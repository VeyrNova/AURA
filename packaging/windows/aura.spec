# Static PyInstaller scaffold. Build only when PyInstaller is installed.
from pathlib import Path
root = Path(SPECPATH).parents[2]
a = Analysis([str(root / 'app' / 'main.py')], pathex=[str(root / 'src')], datas=[(str(root/'app'/'qml'),'app/qml'),(str(root/'app'/'assets'),'app/assets')], hiddenimports=['PySide6.QtMultimedia'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='AURA', console=False)
