# -*- mode: python ; coding: utf-8 -*-
block_cipher = None
import os

files = [
    ('../src/data/data/generated_ui_files/*.ui', 'data/generated_ui_files'),
    ('../src/resources/images/*', 'resources/images'),
    ('../src/resources/ui_files/*', 'resources/ui_files'),
]

a = Analysis(['../main.py'],
             pathex=[],
             binaries=[],
             datas=files,
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
          icon='../src/resources/images/golf-icon.ico',
          )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='main')
