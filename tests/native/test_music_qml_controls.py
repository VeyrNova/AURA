"""Drive the actual MusicCenterView controls through Qt pointer events."""
import math
import os
import tempfile
import unittest
import wave
from pathlib import Path
from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest, QSignalSpy
from aura_native.ui.music_bridge import NativeMusicBridge
from aura_native.ui.module_composition import NativeModuleComposition
from aura_native.weather.service import WeatherService
from aura_native.weather.provider import FakeWeatherProvider
from aura_native.diagnostics.service import DiagnosticsService
from types import SimpleNamespace

ROOT=Path(__file__).parents[2]

class MusicQmlControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        cls.app=QGuiApplication.instance() or QGuiApplication([])

    def test_open_play_pause_resume_stop_from_real_view(self):
        with tempfile.TemporaryDirectory() as directory:
            wav=Path(directory)/'aura-test.wav'
            with wave.open(str(wav),'wb') as out:
                out.setnchannels(1); out.setsampwidth(2); out.setframerate(8000)
                out.writeframes(b'\0\0'*8000*5)
            composition=NativeModuleComposition.build(SimpleNamespace(weather_service=WeatherService(FakeWeatherProvider()),diagnostics_service=DiagnosticsService()),file_picker=lambda: str(wav))
            bridge=composition.music_bridge
            view=QQuickView()
            view.setResizeMode(QQuickView.SizeRootObjectToView)
            composition.install_context(view.rootContext())
            view.rootContext().setContextProperty('auraAssetBase',QUrl.fromLocalFile(str(ROOT/'app/assets')+os.sep).toString())
            view.setSource(QUrl.fromLocalFile(str(ROOT/'app/qml/views/MusicCenterView.qml')))
            self.assertEqual(view.status(),QQuickView.Ready)
            view.resize(1440,1400); view.show(); self.app.processEvents()
            root=view.rootObject()
            def find_item(parent,name):
                if parent.objectName()==name: return parent
                for child in parent.childItems():
                    match=find_item(child,name)
                    if match is not None: return match
                return None
            def click(name):
                item=find_item(root,name)
                self.assertIsNotNone(item,name)
                point=item.mapToScene(QPointF(item.width()/2,item.height()/2))
                print(f'MUSIC_QML_CLICK name={name} x={point.x():.1f} y={point.y():.1f} visible={item.isVisible()}',flush=True)
                QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())))
                self.app.processEvents()
            def wait_for(expected):
                for _ in range(100):
                    self.app.processEvents()
                    if bridge.playing is expected: return True
                    QTest.qWait(10)
                return False
            def wait_loaded():
                for _ in range(200):
                    if bridge._player.mediaStatus().name in ('LoadedMedia','BufferedMedia'): return True
                    QTest.qWait(10)
                return False
            try:
                root.setProperty('page','library'); self.app.processEvents()
                click('nativeMusicOpenTrack')
                self.assertEqual(bridge.currentTitle,'aura-test')
                self.assertEqual(Path(bridge._player.source().toLocalFile()),wav)
                self.assertTrue(wait_loaded())
                self.assertIs(bridge._player.audioOutput(),bridge._audio)
                self.assertIs(view.rootContext().contextProperty('musicBridge'),bridge)
                print('MUSIC_BEFORE status='+bridge._player.mediaStatus().name+' state='+bridge._player.playbackState().name,flush=True)
                spy=QSignalSpy(bridge._player.playbackStateChanged)
                bridge.play(); self.assertTrue(wait_for(True))
                bridge.stop(); self.assertTrue(wait_for(False))
                root.setProperty('page','player'); self.app.processEvents()
                click('nativeMusicPlayPause'); self.assertTrue(wait_for(True),f'QMediaPlayer did not enter PlayingState; status={bridge._player.mediaStatus().name}; error={bridge._player.error().name}')
                click('nativeMusicPlayPause'); self.assertTrue(wait_for(False))
                click('nativeMusicPlayPause'); self.assertTrue(wait_for(True))
                volume=find_item(root,'nativeMusicVolume')
                point=volume.mapToScene(QPointF(volume.width()*.4,volume.height()/2))
                QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())))
                self.app.processEvents()
                self.assertLess(bridge.volume,80)
                self.assertAlmostEqual(bridge._audio.volume(),bridge.volume/100,places=5)
                seek=find_item(root,'nativeMusicSeek')
                point=seek.mapToScene(QPointF(seek.width()*.6,seek.height()/2))
                QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())))
                self.app.processEvents()
                self.assertGreater(bridge.position,1000)
                subdock=QQuickView()
                composition.install_context(subdock.rootContext())
                subdock.rootContext().setContextProperty('auraAssetBase',view.rootContext().contextProperty('auraAssetBase'))
                subdock.setSource(QUrl.fromLocalFile(str(ROOT/'app/qml/components/MusicSubdock.qml')))
                self.assertEqual(subdock.status(),QQuickView.Ready)
                self.assertIs(subdock.rootContext().contextProperty('musicBridge'),bridge)
                subdock.resize(452,104);subdock.show();QTest.qWait(20)
                def sources(item):
                    values=[str(item.property('source') or '')]
                    for child in item.childItems():values.extend(sources(child))
                    return values
                self.assertTrue(any('music-pause-premium.svg' in source for source in sources(subdock.rootObject())))
                button=find_item(subdock.rootObject(),'nativeMusicSubdockPlayPause')
                point=button.mapToScene(QPointF(button.width()/2,button.height()/2))
                QTest.mouseClick(subdock,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())))
                self.assertTrue(wait_for(False))
                self.assertEqual(bridge._player.playbackState().name,'PausedState')
                self.assertTrue(any('music-play-premium.svg' in source for source in sources(root)))
                subdock.close();subdock.setSource(QUrl())
                click('nativeMusicPlayPause');self.assertTrue(wait_for(True))
                click('nativeMusicStop'); self.assertTrue(wait_for(False))
                states=[spy.at(i)[0].name for i in range(spy.count())]
                self.assertIn('PausedState',states)
                print(f'MUSIC_OBSERVED signals={spy.count()} states={states} error={bridge._player.error().name} errorString={bridge._player.errorString()!r} duration={bridge.duration} hasAudio={bridge._player.hasAudio()}',flush=True)
                player=bridge._player
                view.setSource(QUrl())
                view.setSource(QUrl.fromLocalFile(str(ROOT/'app/qml/views/MusicCenterView.qml')))
                self.assertEqual(view.status(),QQuickView.Ready)
                self.assertIs(view.rootContext().contextProperty('musicBridge'),bridge)
                self.assertIs(bridge._player,player)
            finally:
                bridge.shutdown(); view.close()
                bridge._player.deleteLater(); bridge._audio.deleteLater()
                for _ in range(20): QTest.qWait(10); self.app.processEvents()

if __name__=='__main__': unittest.main()
