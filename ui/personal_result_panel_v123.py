from __future__ import annotations
from typing import Any,Mapping
from PySide6.QtCore import QEvent,Qt
from PySide6.QtWidgets import QFrame,QHBoxLayout,QLabel,QPushButton,QScrollArea,QVBoxLayout,QWidget

class PersonalResultPanelV123(QFrame):
    def __init__(self,parent:QWidget):
        super().__init__(parent); self.setObjectName("auraPersonalResultPanelV123"); self.setFrameShape(QFrame.StyledPanel); self.setAttribute(Qt.WA_StyledBackground,True); parent.installEventFilter(self)
        root=QVBoxLayout(self); root.setContentsMargins(18,18,18,18); root.setSpacing(12)
        h=QHBoxLayout(); self.title=QLabel("AURA"); self.count=QLabel(""); close=QPushButton("×"); close.setFixedWidth(36); close.clicked.connect(self.hide)
        h.addWidget(self.title); h.addStretch(1); h.addWidget(self.count); h.addWidget(close); root.addLayout(h)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame)
        self.content=QWidget(); self.cards=QVBoxLayout(self.content); self.cards.setContentsMargins(0,0,0,0); self.cards.setSpacing(10); self.scroll.setWidget(self.content); root.addWidget(self.scroll,1)
        self.hide(); self._sync_geometry()
    def eventFilter(self,watched,event):
        if watched is self.parentWidget() and event.type() in (QEvent.Resize,QEvent.Show,QEvent.WindowStateChange): self._sync_geometry()
        return super().eventFilter(watched,event)
    def _sync_geometry(self):
        p=self.parentWidget()
        if p is None:return
        r=p.rect(); m=18; w=max(520,min(880,int(r.width()*0.48))); self.setGeometry(max(m,r.width()-w-m),m,max(420,w),max(420,r.height()-36)); self.raise_()
    def _clear(self):
        while self.cards.count():
            it=self.cards.takeAt(0); w=it.widget()
            if w is not None:w.deleteLater()
    def _heading(self,k): return {"mail":"MAIL","calendar":"AGENDA","contacts":"CONTACTS","drive":"DRIVE"}.get(k,"RÉSULTATS")
    def _order(self,k): return {"mail":("sender","subject","preview","date_time","read_state"),"calendar":("start_time","title","duration","location_or_meet","participants_optional"),"contacts":("name","organization_role","email","phone"),"drive":("type_icon","name","location","modified","size_optional")}.get(k,())
    def _label(self,f): return {"sender":"De","subject":"Objet","preview":"Aperçu","date_time":"Date","read_state":"État","start_time":"Heure","title":"Titre","duration":"Durée","location_or_meet":"Lieu","participants_optional":"Participants","name":"Nom","organization_role":"Organisation","email":"Email","phone":"Téléphone","type_icon":"Type","location":"Emplacement","modified":"Modifié","size_optional":"Taille"}.get(f,f.replace("_"," ").title())
    def _card(self,k,item:Mapping[str,Any]):
        frame=QFrame(self.content); frame.setFrameShape(QFrame.StyledPanel); lay=QVBoxLayout(frame); lay.setContentsMargins(14,12,14,12); lay.setSpacing(5)
        order=list(self._order(k))
        for f in item:
            if f not in order:order.append(f)
        for f in order:
            v=item.get(f)
            if v in (None,"",[],{}):continue
            if isinstance(v,(list,tuple)):v=", ".join(str(x) for x in v[:8])
            t=str(v); t=t if len(t)<=500 else t[:497]+"..."
            lab=QLabel(f"{self._label(f)} · {t}"); lab.setWordWrap(True); lab.setTextInteractionFlags(Qt.TextSelectableByMouse); lay.addWidget(lab)
        self.cards.addWidget(frame)
    def present(self,payload:Mapping[str,Any]):
        payload=dict(payload or {}); k=str(payload.get("kind") or "generic"); items=payload.get("items") or []; n=int(payload.get("count") or len(items))
        self.title.setText(self._heading(k)); self.count.setText(f"{n} résultat{'s' if n!=1 else ''}"); self._clear()
        for item in list(items)[:50]:self._card(k,item if isinstance(item,Mapping) else {"title":str(item)})
        if not items:
            lab=QLabel(str(payload.get("fallback_text") or "Aucun résultat.")); lab.setWordWrap(True); self.cards.addWidget(lab)
        self.cards.addStretch(1); self._sync_geometry(); self.show(); self.raise_()
