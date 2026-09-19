"""AURA P0.6.5.4 — deterministic local multi-file project intelligence.

This module is deliberately provider-free: no HTTP, no LLM, no shell, no
filesystem traversal. SystemService resolves and extracts authorized direct-child
files first, then passes bounded text sources here.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
import re
from typing import Iterable


class LocalProjectIntelligenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProjectSource:
    file_id: str
    name: str
    text: str
    size_bytes: int = 0
    truncated: bool = False


@dataclass(frozen=True)
class LocalProjectResult:
    mode: str
    query: str
    text: str
    files_considered: int
    files_matched: int
    source_chars: int
    result_chars: int
    provenance: tuple[dict, ...]
    extractive: bool = True
    local_only: bool = True


_STOPWORDS=frozenset({
    'alors','avec','avoir','cela','celle','celles','celui','ceux','comme','dans',
    'des','elle','elles','entre','être','fait','faire','fois','ils','leur','leurs',
    'mais','nous','pour','sans','ses','sont','sur','une','vous','plus','tout',
    'tous','toute','toutes','aux','ces','cet','cette','qui','que','quoi','dont',
    'par','pas','est','les','du','de','la','le','un','et','ou','où','au','en',
    'projet','dossier','fichier','fichiers','résume','resume','résumé','cherche',
    'the','and','for','with','this','that','from','into','are','was','were','have',
    'has','not','but','you','your','our','its','can','will','about','project','file',
})


def _terms(text: str) -> list[str]:
    return [
        token.casefold()
        for token in re.findall(r"[A-Za-zÀ-ÿ0-9_'-]{3,}", str(text or ''))
        if token.casefold() not in _STOPWORDS
    ]


def _clean(text: str) -> str:
    value=re.sub(r'\r\n?', '\n', str(text or ''))
    value=re.sub(r'[ \t]+', ' ', value)
    value=re.sub(r'\n{3,}', '\n\n', value)
    return value.strip()


def _chunks(text: str, *, min_chars: int=24, max_chars: int=760) -> list[str]:
    clean=_clean(text)
    if not clean: return []
    raw=re.split(r'(?<=[.!?])\s+|\n+', clean)
    out=[]
    for item in raw:
        item=item.strip(' \t\r\n•*-')
        if len(item)<min_chars: continue
        if len(item)<=max_chars:
            out.append(item)
        else:
            for start in range(0,len(item),max_chars):
                part=item[start:start+max_chars].strip()
                if len(part)>=min_chars: out.append(part)
    return out


def _summary_for_source(text: str, *, max_chars: int=700) -> str:
    chunks=_chunks(text)
    if not chunks:
        value=_clean(text)
        return value[:max_chars]
    freq=Counter(_terms(text))
    maxf=max(freq.values()) if freq else 1
    ranked=[]
    total=max(1,len(chunks))
    for idx,chunk in enumerate(chunks):
        words=_terms(chunk)
        lexical=(sum(freq.get(w,0)/maxf for w in words)/max(1,len(words))) if words else 0
        position=.18 if idx<max(2,total//8) else 0
        ending=.06 if idx>=max(0,total-2) else 0
        heading=.08 if len(chunk)<100 else 0
        ranked.append((lexical+position+ending+heading,idx,chunk))
    chosen=sorted(ranked,key=lambda x:(x[0],-x[1]),reverse=True)[:4]
    chosen.sort(key=lambda x:x[1])
    parts=[];used=0
    for _score,_idx,chunk in chosen:
        line='• '+chunk
        if parts and used+len(line)+1>max_chars: continue
        parts.append(line);used+=len(line)+1
    return '\n'.join(parts)[:max_chars] or _clean(text)[:max_chars]


def _snippet(text: str, terms: list[str], *, radius: int=190) -> tuple[str,int]:
    source=_clean(text)
    low=source.casefold()
    positions=[]
    for term in terms:
        start=0
        while True:
            pos=low.find(term,start)
            if pos<0: break
            positions.append(pos)
            start=pos+max(1,len(term))
            if len(positions)>=60: break
        if len(positions)>=60: break
    if not positions: return '',0
    positions.sort()
    first=positions[0]
    left=max(0,first-radius);right=min(len(source),first+radius+220)
    snip=re.sub(r'\s+',' ',source[left:right]).strip()
    return snip,len(positions)


def analyze_local_project(
    sources: Iterable[ProjectSource],
    *,
    mode: str,
    query: str='',
    max_result_chars: int=12000,
) -> LocalProjectResult:
    docs=[s for s in list(sources or []) if str(getattr(s,'text','') or '').strip()]
    mode=str(mode or '').strip().casefold()
    query=str(query or '').strip()
    if mode not in {'summary','search','context'}:
        raise LocalProjectIntelligenceError('Mode projet local non pris en charge.')
    if mode in {'search','context'} and not query:
        raise LocalProjectIntelligenceError('Un terme ou une question est nécessaire.')
    if not docs:
        raise LocalProjectIntelligenceError('Aucun contenu textuel local exploitable dans ce projet.')

    provenance=[]
    source_chars=sum(len(s.text) for s in docs)
    output=[]
    matched=0

    if mode=='summary':
        for source in docs:
            summary=_summary_for_source(source.text,max_chars=720)
            if not summary: continue
            block=f'[{source.name}]\n{summary}'
            if output and sum(len(x)+2 for x in output)+len(block)>max_result_chars: break
            output.append(block)
            provenance.append({
                'file_id':source.file_id,'name':source.name,'matches':0,
                'chars':len(source.text),'role':'summary-source',
            })
        matched=len(provenance)

    elif mode=='search':
        terms=list(dict.fromkeys(_terms(query)))[:10]
        if not terms:
            raise LocalProjectIntelligenceError('Le terme de recherche est trop générique.')
        ranked=[]
        for source in docs:
            low=source.text.casefold()
            hits=sum(low.count(t) for t in terms)
            if hits<=0: continue
            snip,count=_snippet(source.text,terms)
            ranked.append((hits,source.name.casefold(),source,snip,count))
        ranked.sort(key=lambda x:(-x[0],x[1]))
        for hits,_name,source,snip,count in ranked:
            block=f'[{source.name}] · {hits} occurrence(s)\n• …{snip}…'
            if output and sum(len(x)+2 for x in output)+len(block)>max_result_chars: break
            output.append(block)
            provenance.append({
                'file_id':source.file_id,'name':source.name,'matches':hits,
                'chars':len(source.text),'role':'search-match',
            })
        matched=len(ranked)
        if not output:
            output=['Aucune occurrence pertinente trouvée dans les fichiers locaux du projet.']

    else:  # context
        terms=list(dict.fromkeys(_terms(query)))[:12]
        if not terms:
            raise LocalProjectIntelligenceError('La question contextuelle est trop générique.')
        candidates=[]
        by_file={}
        for source in docs:
            low=source.text.casefold()
            file_hits=sum(low.count(t) for t in terms)
            if file_hits<=0: continue
            by_file[source.file_id]=(source,file_hits)
            for idx,chunk in enumerate(_chunks(source.text,max_chars=680)):
                folded=chunk.casefold()
                score=sum(folded.count(t) for t in terms)
                if score<=0: continue
                density=score/max(1,len(chunk)/250)
                candidates.append((score+density,source.name.casefold(),idx,source,chunk))
        candidates.sort(key=lambda x:(-x[0],x[1],x[2]))
        seen=set()
        for score,_name,_idx,source,chunk in candidates[:24]:
            key=(source.file_id,chunk.casefold())
            if key in seen: continue
            seen.add(key)
            block=f'[{source.name}]\n• {chunk}'
            if output and sum(len(x)+2 for x in output)+len(block)>max_result_chars: break
            output.append(block)
            if not any(p['file_id']==source.file_id for p in provenance):
                provenance.append({
                    'file_id':source.file_id,'name':source.name,
                    'matches':by_file[source.file_id][1],
                    'chars':len(source.text),'role':'context-source',
                })
            if len(output)>=10: break
        matched=len(by_file)
        if not output:
            output=['Aucun passage local suffisamment pertinent pour cette question.']

    text='\n\n'.join(output)[:max_result_chars]
    return LocalProjectResult(
        mode=mode,query=query,text=text,
        files_considered=len(docs),files_matched=matched,
        source_chars=source_chars,result_chars=len(text),
        provenance=tuple(provenance),extractive=True,local_only=True,
    )
