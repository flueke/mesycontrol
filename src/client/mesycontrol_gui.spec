# -*- mode: python ; coding: utf-8 -*-

import sys


block_cipher = None

binaries = list()

if sys.platform.startswith('win32'):
    binaries = [
            (r'C:/msys64\mingw64\bin\libprotobuf.dll', '.'),
            ]


a = Analysis(['mesycontrol_gui.py'],
             pathex=[],
             binaries=binaries,
             datas=[],
             # pyinstaller does not evaulate __all__ nor do the star imports work
             hiddenimports=[
                 'pyqtgraph.console.template_pyside2',
                 'pyqtgraph.graphicsItems.ViewBox.axisCtrlTemplate_pyside2',
                 'pyqtgraph.graphicsItems.PlotItem.plotConfigTemplate_pyside2',
                 'pyqtgraph.imageview.ImageViewTemplate_pyside2',
                 'mesycontrol.devices.mcfd16',
                 'mesycontrol.devices.mhv4' ,
                 'mesycontrol.devices.mhv4_v20' ,
                 'mesycontrol.devices.mpd4',
                 'mesycontrol.devices.mpd8',
                 'mesycontrol.devices.mprb16',
                 'mesycontrol.devices.mprb16dr',
                 'mesycontrol.devices.mscf16',
                 'mesycontrol.devices.mux16',
                 'mesycontrol.devices.stm16',
                 ],
             runtime_hooks=[],
             excludes=[],
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
          name='mesycontrol_gui',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          icon='mesycontrol/resources/32x32.ico',
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='mesycontrol_gui')

# vim:ft=python
