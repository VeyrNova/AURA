"""
reminder_parser.py
Extrait une date/heure de declenchement et un contenu propre a partir d'une
phrase de rappel en langage naturel (section 13 du cahier des charges).

Volontairement sans dependance externe (pas de librairie type dateparser) :
un jeu de regles couvre les formulations les plus courantes en francais.
Si aucune expression temporelle n'est reconnue, le rappel n'est pas cree et
AURA redemande une precision (fail closed, plus sur qu'un defaut arbitraire).
"""
import re
from datetime import datetime, timedelta

_WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


class ReminderParser:
    def parse(self, text: str, now: datetime = None):
        """Retourne (content, trigger_datetime). trigger_datetime est None si
        aucune expression temporelle n'a ete reconnue."""
        now = now or datetime.now()
        working = re.sub(r"\baura\b[,]?", "", text, flags=re.IGNORECASE)

        resolvers = [
            (r"dans\s+(\d+)\s+minutes?", lambda m: now + timedelta(minutes=int(m.group(1)))),
            (r"dans\s+(\d+)\s+heures?", lambda m: now + timedelta(hours=int(m.group(1)))),
            (r"demain\s+matin", lambda m: self._at(now + timedelta(days=1), 9, 0)),
            (r"demain\s+soir", lambda m: self._at(now + timedelta(days=1), 20, 0)),
            (r"demain\s+(?:à\s+)?(\d{1,2})\s*h(?:eures?)?\s*(\d{2})?",
             lambda m: self._at(now + timedelta(days=1), int(m.group(1)), int(m.group(2) or 0))),
            (r"aujourd['’]hui\s+(?:à\s+)?(\d{1,2})\s*h(?:eures?)?\s*(\d{2})?",
             lambda m: self._at(now, int(m.group(1)), int(m.group(2) or 0))),
            (r"\bdemain\b", lambda m: self._at(now + timedelta(days=1), 9, 0)),
            (r"\b(" + "|".join(_WEEKDAYS) + r")\b(?:\s+(?:à\s+)?(\d{1,2})\s*h(?:eures?)?\s*(\d{2})?)?",
             lambda m: self._next_weekday(now, m.group(1), m.group(2), m.group(3))),
            (r"(?:à\s+)?(\d{1,2})\s*h(?:eures?)?\s*(\d{2})?",
             lambda m: self._today_or_tomorrow(now, int(m.group(1)), int(m.group(2) or 0))),
        ]

        trigger_dt = None
        span = None
        for pattern, resolver in resolvers:
            match = re.search(pattern, working, re.IGNORECASE)
            if match:
                trigger_dt = resolver(match)
                span = match.span()
                break

        if trigger_dt is None:
            return None, None

        content = working[:span[0]] + working[span[1]:]
        content = re.sub(r"(?:rappelle|rapelle|rappele|rappel|rapel)[- ]moi", "", content,
                          flags=re.IGNORECASE)
        content = re.sub(r"^\s*[,]?\s*(?:de|que|d['’])\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s{2,}", " ", content).strip(" ,.")

        return (content or None), trigger_dt

    # ------------------------------------------------------------------
    @staticmethod
    def _at(date: datetime, hour: int, minute: int) -> datetime:
        return date.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def _today_or_tomorrow(self, now: datetime, hour: int, minute: int) -> datetime:
        candidate = self._at(now, hour, minute)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    def _next_weekday(self, now: datetime, weekday_name: str, hour, minute) -> datetime:
        target_index = _WEEKDAYS.index(weekday_name.lower())
        days_ahead = (target_index - now.weekday()) % 7
        days_ahead = days_ahead or 7  # si c'est aujourd'hui, on vise la semaine prochaine
        candidate_date = now + timedelta(days=days_ahead)
        h = int(hour) if hour else 9
        m = int(minute) if minute else 0
        return self._at(candidate_date, h, m)
