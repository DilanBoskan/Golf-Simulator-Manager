# -*- mode: python ; coding: utf-8 -*-
block_cipher = None
import PyInstaller.config
import os

PyInstaller.config.CONF['distpath'] = r'B:\boska\Documents\Dilan\Dropbox\Fiverr\Jobs\Work Exports'
files = [
    r'custom_widgets.py',
    r'database_manager.py',
    r'img\*',
    r'UI Files\*.ui',
    r'UI Files\Stations\*',
]

added_files = []
for file in files:
    destination = os.path.split(file)[0]
    if not destination:
        # File in root
        destination = file

    added_files.append((file, destination))
a = Analysis(['main.py'],
             pathex=[],
             binaries=[],
             datas=added_files,
             hiddenimports=['PySide2.QtXml'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['PyQt5', 'numpy'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='Golf Simulator Manager',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          icon=r'img\golf-icon.ico',
          )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='main')
