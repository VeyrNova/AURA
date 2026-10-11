from __future__ import annotations
import re, unicodedata
from datetime import datetime
from .models import IntentResult
from aura_native.reminders.temporal_fr import parse_french_temporal

class NativeIntentRouter:
    """Pure, local command recognizer. It never touches services or I/O."""
    _open = {
        'mail': ('mail','mails'), 'agenda': ('agenda','calendrier'), 'contacts': ('contacts','contact'),
        'documents': ('documents','fichiers','fichier'), 'search': ('recherche','rechercher'),
        'weather': ('météo','meteo'), 'music': ('musique',), 'diagnostics': ('diagnostics','diagnostic'),
        'maps': ('maps','cartes'), 'notes': ('notes','note'), 'reminders': ('rappels','rappel'),
    }
    def __init__(self, clock=None):
        self.clock = clock
    def _norm(self,text):
        s=' '.join(str(text or '').strip().split()).rstrip('!?.,;:').strip().casefold()
        return unicodedata.normalize('NFC',s).replace('’', "'")
    def parse(self,text, *, source="keyboard"):
        original=str(text or ''); n=self._norm(original)
        if not n: return IntentResult(None,original,n)
        raw=original.strip()
        # Legacy user aliases retained as deterministic Native aliases.
        raw_without_assistant = re.sub(r'^(?:aura|aura[, ]+)\s+', '', raw, flags=re.I).strip()
        if raw_without_assistant != raw:
            raw = raw_without_assistant
            n = self._norm(raw)
        # Lot 013: deterministic local Music controls. These are reversible
        # UI operations and never create PreparedActions or call an LLM.
        if re.match(r'^(?:ouvre|ouvre la|ouvre le)\s+(?:module\s+)?musique$', n):
            return IntentResult('MUSIC_OPEN', original, n, {'module':'music'}, True, False, source)
        if re.match(r'^(?:mets|met)\s+(?:la\s+)?musique\s+(?:en\s+)?pause$|^(?:pause)\s+(?:la\s+)?musique$', n):
            return IntentResult('MUSIC_PAUSE', original, n, {}, True, False, source)
        if re.match(r'^(?:reprends?|continue)\s+(?:la\s+)?musique$', n):
            return IntentResult('MUSIC_RESUME', original, n, {}, True, False, source)
        if re.match(r'^(?:arrête|arrete|stop)\s+(?:la\s+)?musique$', n):
            return IntentResult('MUSIC_STOP', original, n, {}, True, False, source)
        if re.match(r'^(?:piste|musique)\s+(?:suivante|suivant|next)$', n):
            return IntentResult('MUSIC_NEXT', original, n, {}, True, False, source)
        if re.match(r'^(?:piste|musique)\s+(?:précédente|precedente|previous)$', n):
            return IntentResult('MUSIC_PREVIOUS', original, n, {}, True, False, source)
        m = re.match(r'^(?:règle|regle|mets|met)\s+(?:le\s+)?volume\s+(\d{1,3})\s*(?:%|pourcent)?$', n)
        if m: return IntentResult('MUSIC_VOLUME', original, n, {'volume':max(0,min(100,int(m.group(1))))}, True, False, source)
        if re.match(r'^(?:muet|mute|coupe)\s+(?:le\s+)?son$', n):
            return IntentResult('MUSIC_MUTE', original, n, {}, True, False, source)
        m = re.match(r'^(?:avance|positionne|seek)\s+(?:la\s+)?musique\s+à\s+(\d{1,3})\s*(?:%|pourcent)$', n)
        if m: return IntentResult('MUSIC_SEEK', original, n, {'position':max(0,min(100,int(m.group(1))))}, True, False, source)
        m = re.match(r'^(?:joue|jouer|lis|lire)\s+(?:la\s+)?musique\s+(.+)$', raw, re.I)
        if m: return IntentResult('MUSIC_PLAY', original, n, {'query':m.group(1).strip()}, True, False, source)
        # Productivity read commands; writes remain deliberately unsupported
        # in this lot and therefore never enter the Google mutation path.
        if re.match(r'^(?:montre|affiche|liste)\s+(?:mes\s+)?(?:derniers?\s+)?mails?$', n):
            return IntentResult('MAIL_LIST',original,n,{},True,False,source)
        m=re.match(r'^(?:cherche|recherche)\s+(?:les\s+)?mails?\s+(?:de|avec|sur)\s+(.+)$',raw.rstrip('!?.,;:'),re.I)
        if m: return IntentResult('MAIL_SEARCH',original,n,{'query':m.group(1).strip()},True,False,source)
        m=re.match(r'^(?:lis|lire|ouvre|affiche)\s+(?:le\s+)?mail\s+(\S+)$',raw,re.I)
        if m: return IntentResult('MAIL_READ',original,n,{'message_id':m.group(1)},True,False,source)
        if re.match(r'^(?:qu[\'’]ai-je|quels?\s+rendez[- ]vous|montre(?:-moi)?\s+mon\s+agenda)\s+(?:aujourd[\'’]hui|demain)$',n):
            return IntentResult('CALENDAR_FOR_DATE',original,n,{'date':'tomorrow' if 'demain' in n else 'today'},True,False,source)
        if re.match(r'^(?:liste|affiche|montre)\s+(?:mon\s+)?(?:agenda|calendrier|rendez[- ]vous)',n):
            return IntentResult('CALENDAR_LIST',original,n,{},True,False,source)
        m=re.match(r'^(?:cherche|recherche)\s+(?:un\s+)?(?:événement|evenement|rendez[- ]vous)\s+(.+)$',raw.rstrip('!?.,;:'),re.I)
        if m: return IntentResult('CALENDAR_SEARCH',original,n,{'query':m.group(1).strip()},True,False,source)
        if re.match(r'^(?:liste|affiche|montre)\s+(?:mes\s+)?contacts$',n):
            return IntentResult('CONTACT_LIST',original,n,{},True,False,source)
        m=re.match(r'^(?:cherche|recherche|trouve)\s+(.+?)\s+dans\s+(?:mes\s+)?contacts$',raw.rstrip('!?.,;:'),re.I)
        if m: return IntentResult('CONTACT_SEARCH',original,n,{'query':m.group(1).strip()},True,False,source)
        m=re.match(r'^(?:lis|lire|ouvre|affiche)\s+(?:le\s+)?contact\s+(\S+)$',raw,re.I)
        if m: return IntentResult('CONTACT_SHOW',original,n,{'contact_id':m.group(1)},True,False,source)
        m=re.match(r'^(?:ajoute|crée|cree)\s+(?:un\s+)?contact\s+(.+?)(?:\s+avec\s+(?:l[\'’]email|email)\s+([^\s]+))?$',raw,re.I)
        if m:
            return IntentResult('CREATE_CONTACT',original,n,{'display_name':m.group(1).strip(),'emails':([m.group(2)] if m.group(2) else [])},True,True,source)
        m=re.match(r'^(?:modifie|mets?\s+à\s+jour)\s+(?:le\s+)?contact\s+(.+?)\s+(?:avec\s+le\s+nom|nom)\s+(.+)$',raw,re.I)
        if m: return IntentResult('UPDATE_CONTACT',original,n,{'target':m.group(1).strip(),'display_name':m.group(2).strip()},True,True,source)
        m=re.match(r'^supprime(?:z)?\s+(?:le\s+)?contact\s+(.+)$',raw,re.I)
        if m: return IntentResult('DELETE_CONTACT',original,n,{'target':m.group(1).strip()},True,True,source)
        # Safe, deterministic read-only Windows commands. Keep these before
        # broad search/open rules so only explicit semantic phrases match.
        if re.match(r'^(?:quelles?\s+fen[êe]tres?\s+sont\s+ouvertes?|liste(?:r)?\s+les\s+fen[êe]tres?\s+ouvertes?|montre(?:r)?\s+les\s+fen[êe]tres?\s+ouvertes?|quelles?\s+applications?\s+ont\s+une\s+fen[êe]tre\s+ouverte)$', n):
            return IntentResult('PC_LIST_WINDOWS',original,n,{},True,False,source)
        if re.match(r"^(?:quels?\s+processus\s+tournent|liste(?:r)?\s+les\s+processus|quels?\s+programmes?\s+sont\s+en\s+cours\s+d[' ]?ex[ée]cution)$", n):
            return IntentResult('PC_LIST_PROCESSES',original,n,{},True,False,source)
        if re.match(r"^(?:quelle?\s+fen[êe]tre\s+est\s+active|quelle?\s+application\s+est\s+au\s+premier\s+plan|quel\s+programme\s+j[' ]?utilise\s+actuellement)$", n):
            return IntentResult('PC_GET_FOREGROUND_WINDOW',original,n,{},True,False,source)
        for name, pattern in (
            ('CREATE_MEMORY',r'^(?:souviens[- ]toi que|m[ée]morise que|retiens que|garde en m[ée]moire que)\s+(.+)$'),
            ('FORGET_MEMORY',r'^(?:oublie|efface de ta m[ée]moire)\s+(?:le\s+souvenir\s+)?(?:num[ée]ro\s*|n°\s*|#\s*)?(\S.*)$'),
            ('CREATE_NOTE',r'^(?:note que|ajoute une note|cr[ée]e une note)\s*[: -]?\s*(.*)$'),
            ('CREATE_NOTE',r'^prends une note\s*[: -]?\s*(.*)$'),
            ('CREATE_TASK',r'^(?:cr[ée]e|ajoute)\s+(?:une\s+)?t[âa]che\s*[: -]?\s*(.*)$'),
            ('CREATE_TASK',r'^je dois\s+(.+)$'),
            ('COMPLETE_TASK',r'^(?:termine|marque)\s+la t[âa]che\s*(.*)$'),
            ('DELETE_NOTE',r'^supprime(?:z)?\s+la note\s*(.*)$'),
            ('DELETE_REMINDER',r'^supprime(?:z)?\s+le rappel\s*(.*)$'),
        ):
            match=re.match(pattern,raw,re.I)
            if match:
                content=match.group(1).strip()
                return IntentResult(name,original,n,{'raw':content,**({} if content else {'error':'needs_content'})},True,True,source)
        m=re.match(r'^(?:cherche|recherche|trouve)\s+(?:dans\s+)?(?:ma\s+)?m[ée]moire\s+(.+)$',raw,re.I)
        if m: return IntentResult('SEARCH_MEMORY',original,n,{'query':m.group(1).strip()},True,False,source)
        if re.match(r'^(?:affiche|liste|montre)(?:\s+ma|\s+mes)?\s+m[ée]moire$',n) or re.match(r"^(?:qu['’]est-ce que tu sais (?:sur|de) moi|que sais-tu (?:sur|de) moi|montre[- ]moi (?:mes souvenirs|ce que tu sais sur moi)|liste (?:mes souvenirs|ce que tu sais sur moi))$",n):
            return IntentResult('LIST_MEMORY',original,n,{},True,False,source)
        reminder=re.match(r'^(?:rappelle[- ]moi|rappel(?:le)?)[,:]?\s*(.*)$',raw,re.I)
        if reminder:
            body=reminder.group(1).strip()
            # The temporal parser owns all French time forms. Content may be
            # introduced by ``de``; the resolved instant is stored in slots.
            temporal_text = body
            content = body
            # Accept both ``dans 20 minutes de ...`` and ``de ... dans 20
            # minutes`` forms while keeping the content out of the time slot.
            mcontent = re.match(r'^(.+?)\s+de\s+(.+)$', body, re.I)
            if mcontent and not re.match(r'^(dans|demain|apr[èe]s-demain|aujourd|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|ce |cet |le?\s*\d|\d{4}-|[àa]\s*\d)', mcontent.group(1).strip(), re.I):
                mcontent = None
            if mcontent:
                temporal_text, content = mcontent.group(1).strip(), mcontent.group(2).strip()
            elif body.lower().startswith('de '):
                content = body[3:].strip()
                for marker in (r'\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}\b', r'\bdans\s+\d+\s+\w+', r'\bdemain(?:\s+à\s+\d{1,2}h\d{0,2})?\b'):
                    mm=re.search(marker, content, re.I)
                    if mm:
                        temporal_text=content[mm.start():]; content=content[:mm.start()].strip(); break
            result = parse_french_temporal(temporal_text, now=self.clock() if self.clock else None)
            if result.status == 'OK' and content == body and not body.lower().startswith('de '):
                marker = re.search(r'(?:\b(?:dans\s+\d+\s+(?:minutes?|heures?|jours?|semaines?)|demain(?:\s+à\s+\d{1,2}h\d{0,2})?|après-demain(?:\s+à\s+\d{1,2}h\d{0,2})?|aujourd[\' ]hui(?:\s+à\s+\d{1,2}h\d{0,2})?|(?:le\s+)?\d{1,2}[/-]\d{1,2}(?:[/-]\d{4})?(?:\s+à\s+\d{1,2}h\d{0,2})?|(?:le\s+)?\d{1,2}\s+\w+(?:\s+à\s+\d{1,2}h\d{0,2})?|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}|à\s+\d{1,2}h\d{0,2}))', body, re.I)
                content = body[:marker.start()].strip() if marker else ''
            slots={'raw':content, 'temporal_status':result.status}
            if result.status == 'OK': slots['trigger_at']=result.trigger_at
            else: slots['error']=result.error or result.status.lower()
            if result.status == 'OK' and not content:
                slots['error']='needs_content'
            return IntentResult('CREATE_REMINDER',original,n,slots,True,True,source)
        # System Control mutations are only parsed into typed title slots;
        # execution and HWND/PID resolution belong to an injected dispatcher.
        m=re.match(r'^(?:minimise|minimize)\s+(?:la\s+)?fenêtre\s+(.+)$',n)
        if m: return IntentResult('PC_MINIMIZE_WINDOW',original,n,{'title':m.group(1).strip()},True,True,source)
        m=re.match(r'^(?:maximise|maximize)\s+(?:la\s+)?fenêtre\s+(.+)$',n)
        if m: return IntentResult('PC_MAXIMIZE_WINDOW',original,n,{'title':m.group(1).strip()},True,True,source)
        m=re.match(r'^(?:focus|active)\s+(?:la\s+)?fenêtre\s+(.+)$',n)
        if m: return IntentResult('PC_FOCUS_WINDOW',original,n,{'title':m.group(1).strip()},True,True,source)
        m=re.match(r'^ouvre\s+(?:la\s+)?m[ée]t[ée]o(?:\s+(?:[àa]|de)\s+)(.+)$',raw.rstrip('!?.,;:'),re.I)
        if m:
            place=m.group(1).strip(); return IntentResult('OPEN_MODULE',original,n,{'module':'weather','location':place},True,False,source)
        m=re.match(r'^ouvre\s+(?:les\s+)?documents?\s+(?:sur|pour)\s+(.+)$',raw.rstrip('!?.,;:'),re.I)
        if m:
            return IntentResult('OPEN_MODULE',original,n,{'module':'documents','query':m.group(1).strip()},True,False,source)
        m=re.match(r'^(?:cherche|recherche|trouve)\s+(?:un\s+)?document\s+(.+)$',raw.rstrip('!?.,;:'),re.I)
        if m: return IntentResult('DOCUMENTS_SEARCH',original,n,{'query':m.group(1).strip()},True,False,source)
        m=re.match(r'^(?:ouvre|lis|affiche|montre)\s+(?:le\s+)?document\s+(.+)$',raw.rstrip('!?.,;:'),re.I)
        if m: return IntentResult('DOCUMENTS_OPEN',original,n,{'path':m.group(1).strip(),'document_id':m.group(1).strip()},True,False,source)
        m=re.match(r'^ouvre(?:\s+les|\s+mes|\s+le|\s+la)?\s+(.+)$',n)
        if m:
            target=m.group(1)
            for module, aliases in self._open.items():
                if target in aliases: return IntentResult('OPEN_MODULE',original,n,{'module':module},True)
        if n in ('ouvre mes tâches','ouvre mes taches'):
            return IntentResult('OPEN_MODULE',original,n,{'module':'tasks'},True)
        m=re.match(r'^(?:quel temps fait[- ]il|quelle est la météo|quelle météo).*?\s+(?:à|a|de|sur)\s+(.+)$',n)
        if m and len(m.group(1))>1:
            raw=original.strip().rstrip('!?.,;:').strip(); cap=re.search(r'(?:à|a|de|sur)\s+(.+)$',raw,re.I)
            location=(cap.group(1) if cap else m.group(1)).strip(); date=''
            if location.casefold().endswith(' demain'):
                location=location[:-7].strip(); date='tomorrow'
            return IntentResult('WEATHER_QUERY',original,n,{'location':location,'date':date},True)
        m=re.match(r'^m[ée]t[ée]o\s+(?:à|a|de|sur)\s+(.+)$',raw.rstrip('!?.,;:'),re.I)
        if m:
            location=m.group(1).strip(); date=''
            if location.casefold().endswith(' demain'):
                location=location[:-7].strip(); date='tomorrow'
            return IntentResult('WEATHER_QUERY',original,n,{'location':location,'date':date},True)
        m=re.match(r'^(?:cherche|recherche)\s+(.+?)\s+dans mes contacts$',n)
        if m: return IntentResult('CONTACT_SEARCH',original,n,{'query':m.group(1).strip()},True)
        m=re.match(r'^(?:cherche|recherche|trouve)(?:\s+dans mes notes|\s+une note|\s+ma note)\s*(.*)$',raw.rstrip('!?.,;:'),re.I)
        if m and m.group(1).strip(): return IntentResult('SEARCH_NOTE',original,n,{'query':m.group(1).strip()},True)
        m=re.match(r'^(?:cherche|recherche|trouve)\s+(.+?)\s+dans mes notes$',raw.rstrip('!?.,;:'),re.I)
        if m: return IntentResult('SEARCH_NOTE',original,n,{'query':m.group(1).strip()},True)
        m=re.match(r'^(?:cherche|recherche|trouve)\s+(.+?)\s+dans ma m[ée]moire$',raw.rstrip('!?.,;:'),re.I)
        if m: return IntentResult('SEARCH_MEMORY',original,n,{'query':m.group(1).strip()},True,False,source)
        m=re.match(r'^(?:cherche|recherche)\s+(.+?)\s+sur internet$',raw.rstrip('!?.,;:'),re.I)
        if m: return IntentResult('WEB_SEARCH',original,n,{'query':m.group(1).strip()},True)
        m=re.match(r'^(?:cherche|recherche)(?:\s+sur internet)?\s+(.+)$',n)
        if m and len(m.group(1))>1:
            cap=re.sub(r'^(?:cherche|recherche)(?:\s+sur internet)?\s+','',original.strip(),flags=re.I).rstrip('!?.,;:').strip()
            return IntentResult('WEB_SEARCH',original,n,{'query':cap},True)
        if re.match(r'^(?:affiche|liste|montre|montre[- ]moi)(?:\s+mes)?\s+notes$',n): return IntentResult('LIST_NOTES',original,n,{},True)
        if re.match(r'^(?:affiche|liste|montre)(?:\s+mes)?\s+rappels$',n): return IntentResult('LIST_REMINDERS',original,n,{},True)
        if re.match(r'^(?:affiche|liste|montre|ouvre)(?:\s+mes)?\s+t[âa]ches$',n): return IntentResult('LIST_TASKS',original,n,{},True)
        if re.match(r'^liste(?:\s+mes)?\s+documents$',n): return IntentResult('DOCUMENTS_LIST',original,n,{},True)
        m=re.match(r'^(?:rappelle[- ]moi|rappel(?:le)?)[,:]?\s+(.+)$',n)
        if m: return IntentResult('CREATE_REMINDER',original,n,{'raw':m.group(1).strip()},True)
        # Legacy memory/note/task/reminder grammar is deliberately conservative.
        for intent, pattern, confirm in (
            ('CREATE_NOTE',r'^(?:note que|ajoute une note)\s+(.+)$',False),
            ('CREATE_TASK',r'^(?:crée|cree|ajoute)\s+(?:une\s+)?t[âa]che\s*[: -]\s*(.+)$',False),
            ('COMPLETE_TASK',r'^(?:termine|marque)\s+la t[âa]che\s+(.+?)(?:\s+comme\s+termin[ée]e?)?$',True),
            ('DELETE_NOTE',r'^supprime(?:z)?\s+la note\s+(\d+)$',True),
            ('DELETE_REMINDER',r'^supprime(?:z)?\s+le rappel\s+(\d+)$',True),
        ):
            m=re.match(pattern,n)
            if m:return IntentResult(intent,original,n,{'raw':m.group(1).strip()},True,confirm)
        return IntentResult(None,original,n)
