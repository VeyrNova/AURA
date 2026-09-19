from __future__ import annotations

import re
import unicodedata

from config.settings import settings
from tools.models import ToolPlan, ToolResult
from tools.safe_http import SafeHTTPClient
from tools.weather import WeatherTool
from tools.geo_resolver import canonical_geo_query
from tools.maps import MapsTool, extract_maps_request
from tools.web_fetch import WebFetchTool
from tools.web_search import FreeWebSearchTool
from tools.conversation_context import ConversationalToolContext
from tools.knowledge_reference import (
    KnowledgeReferenceTool, extract_definition_subject, extract_explanation_subject, local_reference,
)
from tools.search_intent import extract_explicit_search_query, extract_visual_search_query, requested_result_count


class InternetToolManager:
    """Deterministic planner/executor. The LLM never chooses arbitrary network calls."""

    _URL_RE = re.compile(r"https?://[^\s<>\]\[(){}]+", re.IGNORECASE)

    def __init__(self):
        self.client = SafeHTTPClient(
            timeout=settings.WEB_HTTP_TIMEOUT,
            max_bytes=settings.WEB_MAX_RESPONSE_BYTES,
            max_redirects=settings.WEB_MAX_REDIRECTS,
        )
        self.weather = WeatherTool(self.client)
        self.maps = MapsTool(self.client, default_origin=settings.MAPS_DEFAULT_ORIGIN)
        self.search = FreeWebSearchTool(
            self.client,
            backends=settings.FREE_WEB_SEARCH_BACKENDS,
            region=settings.FREE_WEB_SEARCH_REGION,
            safesearch=settings.FREE_WEB_SEARCH_SAFESEARCH,
            timeout=settings.FREE_WEB_SEARCH_TIMEOUT_SECONDS,
        )
        self.fetch = WebFetchTool(self.client, max_text_chars=settings.WEB_FETCH_MAX_TEXT_CHARS)
        self.knowledge = KnowledgeReferenceTool(
            self.client,
            max_sentences=settings.KNOWLEDGE_REFERENCE_MAX_SENTENCES,
            max_chars=settings.KNOWLEDGE_REFERENCE_MAX_CHARS,
        )
        self.last_sources = ()
        self.context = ConversationalToolContext()

    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize("NFKD", text or "")
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.casefold().replace("’", "'")
        text = re.sub(r"[^a-z0-9:/.'?&=_\-\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    _RELATIVE_WEATHER_LOCATIONS = frozenset({
        "place",
        "sur place",
        "ici",
        "la",
        "là",
        "la bas",
        "là-bas",
        "cet endroit",
        "a cet endroit",
        "à cet endroit",
        "ce lieu",
        "le lieu",
        "la destination",
        "destination",
        "l'arrivee",
        "l'arrivée",
        "arrivee",
        "arrivée",
    })

    @classmethod
    def _is_relative_weather_location(cls, value: str) -> bool:
        normalized = cls._normalize(value or "")
        return normalized in {
            cls._normalize(item) for item in cls._RELATIVE_WEATHER_LOCATIONS
        }

    @classmethod
    def _extract_contextual_weather_location(cls, text: str) -> str:
        """Resolve an explicitly named place before a relative weather phrase."""
        raw = re.sub(r"\s+", " ", str(text or "").strip())
        if not raw:
            return ""

        relative_marker = bool(re.search(
            r"\b(?:sur\s+place|l[aà][ -]bas|[àa]\s+cet\s+endroit|"
            r"sur\s+(?:ce|le)\s+lieu|[àa]\s+(?:la\s+)?destination|"
            r"[àa]\s+l['’ ]?arriv[ée]e)\b",
            raw,
            re.IGNORECASE,
        ))
        if not relative_marker:
            return ""

        weather = r"(?:m[ée]t[ée]o|temps|temp[ée]rature)"
        patterns = (
            rf"\b(?:o[uù]\s+se\s+trouve|o[uù]\s+est)\s+(.+?)\s+(?:avec|et)\s+(?:la\s+)?{weather}\b",
            rf"\b(?:localise|localiser|situe|situer|montre(?:-moi)?|affiche(?:-moi)?)\s+(.+?)\s+(?:avec|et)\s+(?:la\s+)?{weather}\b",
            rf"\b(?:pour|concernant)\s+(.+?)\s+(?:avec|et)\s+(?:la\s+)?{weather}\b",
        )
        for pattern in patterns:
            match = re.search(pattern, raw, re.IGNORECASE)
            if not match:
                continue
            candidate = re.sub(r"\s+", " ", match.group(1)).strip(" ,.;?!")
            candidate = re.sub(
                r"\s+(?:aujourd['’]hui|demain|maintenant|actuellement)$",
                "",
                candidate,
                flags=re.IGNORECASE,
            ).strip()
            if (
                2 <= len(candidate) <= 120
                and not cls._is_relative_weather_location(candidate)
            ):
                return candidate
        return ""

    @classmethod
    def resolve_weather_location(cls, text: str, candidate: str = "") -> str:
        """Return an explicit weather place or empty string; never geocode pronouns."""
        explicit = str(candidate or "").strip(" ,.;?!")
        if explicit and not cls._is_relative_weather_location(explicit):
            return explicit

        contextual = cls._extract_contextual_weather_location(text)
        if contextual:
            return contextual
        return ""

    @classmethod
    def _extract_weather_location(cls, text: str) -> str:
        # Require an explicit place. AURA does not infer user geolocation.
        normalized_full = cls._normalize(text or "")

        # Resolve "Toulon ... météo actuelle sur place" before a generic
        # regex can capture only the trailing word "place".
        contextual = cls._extract_contextual_weather_location(text)
        if contextual:
            return contextual
        if any(phrase in normalized_full for phrase in (
            "meteo a l'arrivee", "meteo a l arrivee", "meteo sur place",
            "meteo actuelle sur place", "meteo aujourd'hui sur place",
            "meteo aujourd hui sur place", "meteo demain sur place",
            "meteo a destination", "meteo a la destination", "weather on arrival",
        )):
            return ""
        patterns = (
            r"(?:quelle|quel)\s+(?:est\s+la\s+)?m[ée]t[ée]o(?:\s+fait[- ]il)?\s+(?:à|a)\s+(.+?)[?.!]*$",
            r"(?:m[ée]t[ée]o|temps)(?:\s+(?:actuelle?|aujourd['’]hui|demain))?\s+(?:à|a|pour|sur)\s+(.+?)[?.!]*$",
            r"temp[ée]rature(?:\s+(?:actuelle?|aujourd['’]hui|demain))?\s+(?:à|a|sur)\s+(.+?)[?.!]*$",
            # AURA P0.8.5.4.7.6.1.5 — EXPLICIT WEATHER LOCATION ROUNDTRIP
            r"quel temps fait[- ]il(?:\s+(?:actuellement|maintenant|aujourd[\'’]hui))?\s+(?:à|a)\s+(.+?)[?.!]*$",
            r"(?:va[- ]t[- ]il|est[- ]ce qu['’]il va)\s+pleuvoir(?:\s+(?:aujourd['’]hui|demain))?\s+(?:à|a)\s+(.+?)[?.!]*$",
            r"weather\s+(?:in|at|for)\s+(.+?)[?.!]*$",
            r"(?:m[ée]t[ée]o|weather)(?:\s+(?:aujourd['’]hui|demain))?\s+([A-Za-zÀ-ÿ][^?.!]*)[?.!]*$",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                # The permissive short form must not mistake temporal/question
                # fragments (e.g. "météo fait-il aujourd'hui ?") for a city.
                candidate = re.sub(r"\s+(?:aujourd['’]hui|demain|maintenant)$", "", candidate, flags=re.IGNORECASE).strip()
                normalized_candidate = cls._normalize(candidate)
                invalid = {
                    "aujourd'hui", "aujourd hui", "demain", "maintenant", "actuellement",
                    "fait il", "fait-il", "fait il aujourd'hui", "fait il aujourd hui",
                    "fait il demain", "fait-il demain", "ici", "chez moi", "ma position",
                    "ma position locale", "position locale", "autour de moi", "près de moi", "pres de moi",
                    "l'arrivée", "l arrivee", "arrivée", "arrivee", "à l'arrivée", "a l arrivee",
                    "la destination", "destination", "sur place", "place",
                    "là-bas", "la bas", "cet endroit", "ce lieu", "le lieu",
                }
                implicit_local = any(
                    token in normalized_candidate
                    for token in (
                        "position locale", "ma position", "chez moi", "autour de moi", "pres de moi",
                        "arrivee", "destination", "sur place", "la bas",
                    )
                )
                if (
                    normalized_candidate in invalid
                    or normalized_candidate.startswith("fait il ")
                    or normalized_candidate.startswith("fait-il ")
                    or implicit_local
                ):
                    continue
                resolved = cls.resolve_weather_location(text, candidate)
                if resolved:
                    return resolved
        return ""

    def plan(self, text: str) -> ToolPlan | None:
        original = (text or "").strip()
        normalized = self._normalize(original)
        if not normalized:
            return None

        # Patch 26.6 — AI research routing lock. An explicit request to search
        # always becomes a Web-search plan before definitions, Agent routing or
        # any LLM path. The plan is returned even when the engine is disabled so
        # execution can fail closed with a visible diagnostic instead of letting
        # a local model answer from memory.
        explicit_query = extract_explicit_search_query(original)
        if explicit_query:
            self.context.clear()
            count = requested_result_count(original, default=settings.WEB_SEARCH_RESULT_COUNT, maximum=8)
            return ToolPlan(
                "web_search", "WEB_SEARCH",
                {
                    "query": explicit_query,
                    "count": count,
                    "explicit_research": True,
                    "engine": "free-web-search",
                },
                "web_search",
            )

        # v0.7.0.9: explicit definitions are grounded before the conversational
        # LLM. A small audited local core works offline; other terms may use a
        # fixed read-only French Wikipedia endpoint when controlled Internet is
        # enabled. The LLM never chooses the destination.
        if settings.KNOWLEDGE_REFERENCE_ENABLED:
            subject = extract_definition_subject(original)
            if not subject:
                # v0.7.0.15.1: source-backed explanations run before the LLM.
                # This removes the 90s llama3.1 cold-load path observed for
                # simple factual voice questions such as "Pourquoi le ciel est bleu ?".
                subject = extract_explanation_subject(original)
            if subject:
                self.context.clear()
                has_local = local_reference(subject) is not None
                allow_web = bool(settings.INTERNET_TOOLS_ENABLED and settings.KNOWLEDGE_REFERENCE_WEB_ENABLED)
                return ToolPlan(
                    "knowledge_reference",
                    "KNOWLEDGE_REFERENCE_LOCAL" if has_local or not allow_web else "WEB_KNOWLEDGE_REFERENCE",
                    {"subject": subject, "allow_web": bool(allow_web and not has_local)},
                    "knowledge_reference",
                )

        if not settings.INTERNET_TOOLS_ENABLED:
            return None

        followup = self.context.plan_followup(original)
        if followup is not None:
            return followup

        url_match = self._URL_RE.search(original)
        if url_match and settings.WEB_FETCH_ENABLED:
            return ToolPlan("web_fetch", "WEB_FETCH", {"url": url_match.group(0).rstrip(".,;!?")}, "web_fetch")

        maps_request = extract_maps_request(original) if settings.MAPS_TOOL_ENABLED else None
        # AURA P0.8.5.4.7.5 — EXPLICIT ROUTE PAIR RECOVERY
        # The legacy extractor remains authoritative. This deterministic fallback
        # only runs when it returned no Maps request and the user explicitly asks
        # for a route/trip with an origin -> destination pair.
        if settings.MAPS_TOOL_ENABLED and not maps_request:
            _p085475_text = " ".join(str(original or "").strip().split())
            _p085475_norm = _p085475_text.casefold()
            _p085475_route_intent = any(
                token in _p085475_norm
                for token in (
                    "itinéraire", "itineraire", "trajet", "directions",
                    "calculer la route", "calcule la route",
                )
            )
            if _p085475_route_intent:
                import re as _p085475_re
                _p085475_pair = _p085475_re.search(
                    r"\b(?:de|depuis)\s+(?P<origin>.+?)\s+(?:à|a|vers)\s+"
                    r"(?P<destination>.+?)(?:[?.!,;]|$)",
                    _p085475_text,
                    flags=_p085475_re.IGNORECASE,
                )
                if _p085475_pair:
                    _p085475_origin = _p085475_pair.group("origin").strip(" \t\r\n,.;:!?")
                    _p085475_destination = _p085475_pair.group("destination").strip(" \t\r\n,.;:!?")
                    if _p085475_origin and _p085475_destination:
                        _p085475_mode = "driving"
                        if any(token in _p085475_norm for token in ("à pied", "a pied", "marche", "walking")):
                            _p085475_mode = "walking"
                        elif any(token in _p085475_norm for token in ("vélo", "velo", "bicyclette", "bicycling")):
                            _p085475_mode = "bicycling"
                        elif any(token in _p085475_norm for token in ("transport en commun", "transit", "bus", "train")):
                            _p085475_mode = "transit"
                        maps_request = {
                            "action": "directions",
                            "origin": _p085475_origin,
                            "destination": _p085475_destination,
                            "travelmode": _p085475_mode,
                        }
        if maps_request:
            action = str(maps_request.get("action") or "")
            if action == "directions":
                return ToolPlan("maps", "MAPS_DIRECTIONS", maps_request, "maps")
            if action == "locate":
                return ToolPlan("maps", "MAPS_LOCATE", maps_request, "maps")

        location = self._extract_weather_location(original)
        weather_explicit = any(term in normalized for term in ("meteo", "quel temps", "pleuvoir", "weather", "forecast", "temperature dehors", "temperature exterieure"))
        temperature_with_place = bool(location and "temperature" in normalized)
        if (weather_explicit or temperature_with_place) and settings.WEATHER_TOOL_ENABLED:
            tomorrow = "demain" in normalized or "tomorrow" in normalized
            return ToolPlan("weather", "WEB_WEATHER", {"location": canonical_geo_query(location), "tomorrow": tomorrow}, "weather")

        # v0.7.0.15.3 Visual Tool First: list/place/product/comparison requests
        # that depend on real-world information are routed to a source tool before
        # any visual LLM profile. This prevents the 75s llama3.1 timeout observed
        # for "5 lieux à visiter autour de Vidauban" and keeps XTTS warm.
        visual_query = extract_visual_search_query(original)
        if settings.WEB_SEARCH_ENABLED and visual_query:
            count = requested_result_count(original, default=settings.WEB_SEARCH_RESULT_COUNT, maximum=8)
            return ToolPlan(
                "web_search", "WEB_SEARCH",
                {"query": visual_query, "count": count}, "web_search",
            )

        # Current-news requests can use the configured search provider. Other
        # live categories remain under Grounded Intelligence until dedicated
        # structured tools exist.
        if settings.WEB_SEARCH_ENABLED and any(term in normalized for term in ("dernieres actualites", "actualites du jour", "actualite aujourd", "news aujourd")):
            return ToolPlan("web_search", "WEB_SEARCH", {"query": original}, "news")
        return None

    def execute(self, plan: ToolPlan) -> ToolResult:
        if plan.name == "weather":
            result = self.weather.execute(str(plan.args.get("location") or ""), tomorrow=bool(plan.args.get("tomorrow")))
        elif plan.name == "maps":
            if plan.action == "MAPS_LOCATE":
                result = self.maps.locate(str(plan.args.get("query") or ""))
            else:
                result = self.maps.directions(
                    str(plan.args.get("destination") or ""),
                    origin=str(plan.args.get("origin") or ""),
                    travelmode=str(plan.args.get("travelmode") or "driving"),
                )
        elif plan.name == "web_search":
            explicit_research = bool(plan.args.get("explicit_research"))
            requested = int(plan.args.get("count") or settings.WEB_SEARCH_RESULT_COUNT)
            if explicit_research and not settings.INTERNET_TOOLS_ENABLED:
                result = ToolResult(
                    False,
                    "Tu m'as demandé de faire une recherche, mais le moteur de recherche Internet d'AURA est désactivé. Je ne vais pas remplacer cette recherche par une réponse inventée du modèle local.",
                    "web_search",
                    "research_engine_disabled",
                    expected_items=requested,
                    complete=False,
                )
            elif explicit_research and not settings.WEB_SEARCH_ENABLED:
                result = ToolResult(
                    False,
                    "Tu m'as demandé de faire une recherche, mais la recherche Web d'AURA est désactivée. Je ne vais pas remplacer cette recherche par une réponse inventée du modèle local.",
                    "web_search",
                    "research_engine_disabled",
                    expected_items=requested,
                    complete=False,
                )
            else:
                result = self.search.execute(
                    str(plan.args.get("query") or ""),
                    count=requested,
                )
        elif plan.name == "web_fetch":
            result = self.fetch.execute(str(plan.args.get("url") or ""))
        elif plan.name == "knowledge_reference":
            result = self.knowledge.execute(
                str(plan.args.get("subject") or ""),
                allow_web=bool(plan.args.get("allow_web", True)),
            )
        else:
            result = ToolResult(False, "Outil Internet inconnu : requête refusée.", "web", "unknown_tool")
        self.last_sources = tuple(result.sources)
        return result

    def observe_result(self, plan: ToolPlan | None, result: ToolResult) -> None:
        """Update the short-lived conversational tool context on the UI thread."""
        self.context.observe(plan, result)
