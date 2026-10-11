from __future__ import annotations
import re
from datetime import date, datetime, time, timedelta
from aura_native.tools.models import ToolRouteResult

_WEEKDAYS={"lundi":0,"mardi":1,"mercredi":2,"jeudi":3,"vendredi":4,"samedi":5,"dimanche":6}

class ToolRouter:
    def __init__(self, registry): self.registry=registry
    def _day(self, folded):
        today=date.today()
        if "demain" in folded: return today+timedelta(days=1)
        for label,weekday in _WEEKDAYS.items():
            if re.search(r"\b"+label+r"\b",folded):
                return today+timedelta(days=(weekday-today.weekday()) % 7 or 7)
        return None
    def _time(self, text):
        match=re.search(r"\b(?:à|a|de)\s*(\d{1,2})(?:h(?:(\d{2}))?)?",text,re.I)
        if not match:return None
        hour,minute=int(match.group(1)),int(match.group(2) or 0)
        return time(hour,minute) if hour<24 and minute<60 else None
    def _route(self,name,arguments=None,reason=""):
        return ToolRouteResult(True,name,arguments or {},bool(reason),reason)
    def _event_arguments(self,text,folded):
        day=self._day(folded); start_time=self._time(text)
        interval=re.search(r"\bde\s*(\d{1,2})h?(\d{2})?\s*(?:à|a)\s*(\d{1,2})h?(\d{2})?",text,re.I)
        if not day or not start_time:return None
        duration=re.search(r"\bpendant\s+(\d+)\s*(?:h|heure|heures|min|minutes)(?:\s*(?:et|ou)\s*(\d+)\s*(?:min|minutes))?",folded,re.I)
        duration_minutes=None
        if duration:
            unit=duration.group(0); first=int(duration.group(1)); duration_minutes=first*60 if re.search(r"\d+\s*(?:h|heure)",unit) else first
            if duration.group(2): duration_minutes=(first*60)+int(duration.group(2))
        duration_hm=re.search(r"\bpendant\s+(\d+)h(\d{1,2})\b",folded,re.I)
        if duration_hm: duration_minutes=int(duration_hm.group(1))*60+int(duration_hm.group(2))
        if interval:
            start_time=time(int(interval.group(1)),int(interval.group(2) or 0)); end_time=time(int(interval.group(3)),int(interval.group(4) or 0))
        else:end_time=(datetime.combine(day,start_time)+timedelta(minutes=duration_minutes or 60)).time()
        title=re.sub(r"^(?:ajoute|crée|créer|cree|creer)\s+", "", text, flags=re.I)
        title=title.strip(" .,!?;:")
        title=re.sub(r"^(?:un|une)\s+(?:rendez-vous|événement|evenement|réunion|reunion)\s+", "", title, flags=re.I)
        title=re.sub(r"^(?:demain|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+(?:à|a)\s+\d{1,2}(?:h\d{1,2})?\s+(?:un|une)\s+(?:rendez-vous|événement|evenement|réunion|reunion)\s+", "", title, flags=re.I)
        title=re.sub(r"\s+pendant\s+\d+\s*(?:h\d{0,2}|heure?s?|minutes?|min)(?:\s*(?:et|ou)\s*\d+\s*(?:minutes?|min))?\s*$", "", title, flags=re.I)
        title=re.sub(r"^(?:demain|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+[^A-Za-z0-9\s]\s+\d{1,2}(?:h\d{1,2})?\s+(?:un|une)\s+(?:rendez-vous|événement|evenement|réunion|reunion)\s+", "", title, flags=re.I)
        title=re.sub(r"^(?:demain|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche).*?rendez-vous\s+", "", title, flags=re.I)
        title=re.sub(r"^(?:demain|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche).*?(?:événement|evenement|réunion|reunion)\s+", "", title, flags=re.I)
        title=re.split(r"\s+(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|demain)\b|\s+(?:à|a|de)\s+\d",title,1,flags=re.I)[0].strip(" .,!?")
        if not title:return None
        tz=datetime.now().astimezone().strftime("%z"); tz=tz[:3]+":"+tz[3:]
        return {"title":title,"start":datetime.combine(day,start_time).isoformat()+tz,"end":datetime.combine(day,end_time).isoformat()+tz,"timezone":tz}
    def _target(self,text,verb):
        value=re.sub(r"^.*?"+verb+r"\s+(?:mon|ma|mes|la|le|une?)?\s*", "", text, flags=re.I).strip(" .,!?")
        value=re.sub(r"^(?:rendez-vous|réunion|reunion|tâche|tache)\s+", "", value, flags=re.I).strip()
        return value if value and value.casefold() not in {"rendez-vous","réunion","reunion","tâche","tache"} else ""
    def route(self, prompt):
        text=str(prompt or "").strip(); folded=text.casefold()
        weather=any(word in folded for word in ("météo","meteo","temps fera","temps fait","pleuv","parapluie","température","temperature","fera-t-il chaud"))
        if weather:
            match=re.search(r"\b(?:à|a)\s+([A-Za-zÀ-ÿ'\- ]+?)(?:\s+(?:demain|vendredi|samedi|dimanche|lundi|mardi|mercredi|jeudi)|[?!.,]|$)", text, re.I)
            if match:
                location=match.group(1).strip(" ,.?")
                if len(location)>=2:return self._route("weather.get_forecast",{"location":location,"date":((date.today()+timedelta(days=1)).isoformat() if "demain" in folded else "")})
            return None
        if re.search(r"\b(ajoute|crée|créer|cree|creer)\b",folded) and (any(x in folded for x in ("réunion","reunion","rendez-vous","dentiste","événement","evenement")) or self._event_arguments(text,folded) is not None):
            arguments=self._event_arguments(text,folded)
            return self._route("calendar.prepare_create_event",arguments,"date_and_time_required" if arguments is None else "")
        if re.search(r"\b(modifie|décale|decale)\b",folded):
            target=self._target(text,r"(?:modifie|décale|decale)")
            return self._route("calendar.prepare_update_event",{"target":target},"event_target_required" if not target else "")
        if re.search(r"\b(supprime|efface)\b",folded) and any(x in folded for x in ("réunion","reunion","rendez-vous","dentiste","événement","evenement")):
            target=self._target(text,r"(?:supprime|efface)")
            return self._route("calendar.prepare_delete_event",{"target":target},"event_target_required" if not target else "")
        if any(x in folded for x in ("quand suis-je libre","est-ce que je suis libre")):
            day=self._day(folded)
            part="afternoon" if "après-midi" in folded else "morning" if "matin" in folded else ""
            return self._route("calendar.find_free_time",{"date":day.isoformat() if day else "","part_of_day":part},"date_required" if day is None else "")
        if any(x in folded for x in ("qu'est-ce que j'ai","qu est-ce que j ai")) and self._day(folded): return self._route("calendar.get_day",{"date":self._day(folded).isoformat()})
        if any(x in folded for x in ("prochains rendez-vous","mes rendez-vous","mon agenda")): return self._route("calendar.list_events")
        if re.search(r"\b(marque|termine)\b",folded) and "tâche" in folded or "comme terminé" in folded:
            target=re.sub(r"\b(?:marque|termine)\b", "", text, flags=re.I); target=re.sub(r"\b(?:la\s+)?tâche\b|\bcomme terminé\b", "", target, flags=re.I).strip(" .,!?")
            return self._route("tasks.prepare_complete",{"target":target},"task_target_required" if not target else "")
        if re.search(r"\b(supprime|efface)\b",folded) and "tâche" in folded:
            target=self._target(text,r"(?:supprime|efface)")
            return self._route("tasks.prepare_delete",{"target":target},"task_target_required" if not target else "")
        if re.search(r"\b(ajoute|rappelle-moi)\b",folded) and ("tâche" in folded or "rappelle-moi" in folded):
            title=re.sub(r"^(?:ajoute\s+(?:(?:la|une)\s+)?tâche\s*|rappelle-moi\s+(?:de\s*)?)", "", text, flags=re.I).strip(" .,!?")
            return self._route("tasks.prepare_create",{"title":title},"task_title_required" if not title else "")
        if "quelles sont mes tâches" in folded or "quelles sont mes taches" in folded:return self._route("tasks.list")
        return None
    def execute_for(self, prompt):
        """Compatibility path for the pre-A3.3 AgentService; `route` never executes."""
        route=self.route(prompt)
        return None if route is None else self.registry.execute(route["name"], route["payload"])
