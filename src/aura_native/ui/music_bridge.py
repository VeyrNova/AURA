"""Small native QtMultimedia bridge shared by Music view and mini-player."""
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot, Property, QAbstractListModel, QModelIndex, Qt, QUrl, QCoreApplication
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

class MusicListModel(QAbstractListModel):
    ItemIdRole=Qt.UserRole+1; TitleRole=Qt.UserRole+2; PathRole=Qt.UserRole+3
    def __init__(self,parent=None): super().__init__(parent); self.items=[]
    def rowCount(self,parent=QModelIndex()): return 0 if parent.isValid() else len(self.items)
    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid() or index.row()>=len(self.items): return None
        item=self.items[index.row()]; return item.get({self.ItemIdRole:'itemId',self.TitleRole:'title',self.PathRole:'path'}.get(role,''))
    def roleNames(self): return {self.ItemIdRole:b'itemId',self.TitleRole:b'title',self.PathRole:b'path'}
    def replace(self,items):
        self.beginResetModel(); self.items=list(items); self.endResetModel()

class NativeMusicBridge(QObject):
    playingChanged=Signal(); stateChanged=Signal(); currentChanged=Signal(); positionChanged=Signal(); durationChanged=Signal(); volumeChanged=Signal(); mutedChanged=Signal(); errorChanged=Signal()
    def __init__(self,parent=None,*,file_picker=None):
        super().__init__(parent); self.model=MusicListModel(self); self.libraryModel=self.model; self._items=[]; self._index=-1; self._volume=80; self._error=''; self._file_picker=file_picker; self._player=QMediaPlayer(self); self._audio=QAudioOutput(self); self._player.setAudioOutput(self._audio); self._audio.setVolume(.8)
        self._player.playbackStateChanged.connect(lambda _ : (self.playingChanged.emit(), self.stateChanged.emit()))
        self._player.mediaStatusChanged.connect(lambda _ : self.stateChanged.emit())
        self._player.sourceChanged.connect(lambda _ : self.currentChanged.emit())
        self._player.positionChanged.connect(lambda _: self.positionChanged.emit()); self._player.durationChanged.connect(lambda _: self.durationChanged.emit()); self._player.errorOccurred.connect(self._on_error)
    def _on_error(self,_,error_string): self._error=str(error_string or 'audio_error'); print('MUSIC_ERROR code=backend',flush=True); self.errorChanged.emit()
    @Property(bool,notify=playingChanged)
    def playing(self): return self._player.playbackState()==QMediaPlayer.PlaybackState.PlayingState
    @Property(str,notify=stateChanged)
    def playbackState(self): return {QMediaPlayer.PlaybackState.PlayingState:'PLAYING', QMediaPlayer.PlaybackState.PausedState:'PAUSED', QMediaPlayer.PlaybackState.StoppedState:'STOPPED'}.get(self._player.playbackState(),'UNKNOWN')
    @Property(str,notify=stateChanged)
    def mediaStatus(self): return self._player.mediaStatus().name.upper()
    @Property(str,notify=currentChanged)
    def currentSource(self): return self._player.source().toLocalFile()
    @Property(str,notify=currentChanged)
    def currentId(self): return self._items[self._index]['itemId'] if 0 <= self._index < len(self._items) else ''
    @Property(str,notify=currentChanged)
    def currentTitle(self): return self._items[self._index]['title'] if 0 <= self._index < len(self._items) else ''
    @Property(str,notify=currentChanged)
    def currentArtist(self): return ''
    @Property(str,notify=currentChanged)
    def currentAlbum(self): return ''
    @Property(str,notify=currentChanged)
    def currentCover(self): return ''
    @Property(str,constant=True)
    def currentExtension(self): return ''
    @Property(str,constant=True)
    def currentYear(self): return ''
    @Property(bool,constant=True)
    def currentFavorite(self): return False
    @Property(bool,constant=True)
    def shuffle(self): return False
    @Property(str,constant=True)
    def repeatMode(self): return 'off'
    @Property(bool,constant=True)
    def resumeEligible(self): return False
    @Property(str,constant=True)
    def resumeTitle(self): return ''
    @Property(str,constant=True)
    def resumePositionLabel(self): return '0:00 / 0:00'
    @Property('QVariantList',constant=True)
    def collections(self): return []
    @Property('QVariantList',constant=True)
    def history(self): return []
    @Property(str,constant=True)
    def hotkeysLabel(self): return 'NATIVE'
    @Property(str,constant=True)
    def smtcLabel(self): return 'NATIVE'
    @Property(int,notify=positionChanged)
    def position(self): return self._player.position()
    @Property(int,notify=durationChanged)
    def duration(self): return self._player.duration()
    @Property(float,notify=positionChanged)
    def progress(self): return self.position/self.duration if self.duration>0 else 0.0
    @Property(str,notify=positionChanged)
    def positionLabel(self): return f'{self.position//60000}:{(self.position//1000)%60:02d}'
    @Property(str,notify=durationChanged)
    def durationLabel(self): return f'{self.duration//60000}:{(self.duration//1000)%60:02d}'
    @Property(int,notify=volumeChanged)
    def volume(self): return self._volume
    @Property(bool,notify=mutedChanged)
    def muted(self): return self._audio.isMuted()
    @Property(int,constant=True)
    def playlistCount(self): return len(self._items)
    @Property(bool,constant=True)
    def available(self): return True
    @Slot(str,result=bool)
    def loadMusic(self,path):
        p=Path(str(path or ''))
        if not p.is_file(): self._error='file_not_found'; print('MUSIC_LOAD_RESULT success=false',flush=True); self.errorChanged.emit(); return False
        key=str(p.resolve()); found=next((i for i,x in enumerate(self._items) if x['itemId']==key),-1)
        if found < 0: self._items.append({'itemId':key,'title':p.stem,'path':key}); found=len(self._items)-1; self.model.replace(self._items)
        self._index=found; self._player.setSource(QUrl.fromLocalFile(key)); self.currentChanged.emit(); print('MUSIC_LOAD_RESULT success=true',flush=True); return True
    @Slot()
    def pickTrack(self):
        if self._file_picker is None:
            from PySide6.QtWidgets import QFileDialog
            path,_=QFileDialog.getOpenFileName(None,'Ouvrir un fichier audio','','Audio (*.wav *.mp3 *.flac *.ogg *.m4a)')
        else:
            path=self._file_picker()
        return self.loadMusic(path) if path else False
    @Slot()
    def play(self): self._player.play(); print('MUSIC_PLAYBACK_STATE state=playing',flush=True)
    @Slot()
    def pause(self): self._player.pause(); print('MUSIC_PLAYBACK_STATE state=paused',flush=True)
    @Slot()
    def stop(self): self._player.stop(); print('MUSIC_PLAYBACK_STATE state=stopped',flush=True)
    @Slot()
    def togglePlay(self): self.pause() if self.playing else self.play()
    @Slot(str)
    def playId(self,item_id): self.play()
    @Slot(float)
    def seekPercent(self,value):
        if self.duration <= 0: self._error='UNKNOWN_DURATION'; self.errorChanged.emit(); return
        self._player.setPosition(int(max(0,min(100,float(value)))*self.duration/100))
    @Slot(int)
    def setVolume(self,value): self._volume=max(0,min(100,int(value))); self._audio.setVolume(self._volume/100); self.volumeChanged.emit()
    @Slot()
    def mute(self): self._audio.setMuted(True); self.mutedChanged.emit()
    @Slot()
    def unmute(self): self._audio.setMuted(False); self.mutedChanged.emit()
    @Slot()
    def toggleMute(self): self.unmute() if self.muted else self.mute()
    @Slot()
    def next(self):
        if self._index + 1 < len(self._items): self._index += 1; self._player.setSource(QUrl.fromLocalFile(self._items[self._index]['path'])); self.currentChanged.emit(); self.play()
    @Slot()
    def previous(self):
        if self._index > 0: self._index -= 1; self._player.setSource(QUrl.fromLocalFile(self._items[self._index]['path'])); self.currentChanged.emit(); self.play()
    @Slot()
    def resumePlayback(self): self.play()
    @Slot()
    def clearResume(self): pass
    @Slot()
    def toggleShuffle(self): pass
    @Slot()
    def cycleRepeat(self): pass
    @Slot(str,bool)
    def setFavorite(self,_,__): pass
    @Slot()
    def clearHistory(self): pass
    @Slot()
    def clearPlaylist(self): self._items=[]; self._index=-1; self.model.replace([]); self._player.stop(); self.currentChanged.emit()
    @Slot()
    def pickFolder(self): return False
    @Slot()
    def playIndex(self,index): self.play()
    @Slot(str)
    def playNext(self,_): self.play()
    @Slot(str)
    def removeItem(self,item_id): self.clearPlaylist()
    @Slot(str,str,bool,bool)
    def setLibraryView(self,query,sort,favorites,duplicates): pass
    @Slot()
    def refreshCollections(self): pass
    @Slot()
    def refreshMetadata(self): pass
    @Slot(str)
    def loadCollection(self,_): pass
    @Slot(str)
    def deleteCollection(self,_): pass
    @Slot(str)
    def saveCollection(self,_): pass
    @Slot()
    def importM3U(self): return False
    @Slot()
    def exportM3U(self): return False
    @Slot(str, int)
    def moveItem(self,_,__): pass
    @Slot()
    def refreshAll(self): pass
    def shutdown(self):
        self._player.stop(); self._player.setSource(QUrl()); QCoreApplication.processEvents()
