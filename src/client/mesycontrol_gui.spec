# -*- mode: python ; coding: utf-8 -*-

import sys


block_cipher = None

binaries = list()

if sys.platform.startswith('win32'):
    binaries = [
            (r'C:/msys64\mingw64\bin\libprotobuf.dll', '.'),
            ]


a_mc_gui = Analysis(['mesycontrol_gui.py'],
             pathex=[],
             binaries=binaries,
             datas=[],
             # pyinstaller does not evaulate __all__ nor do the star imports work
             hiddenimports=[
                 'google.protobuf.text_format',
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
                 'mesycontrol.mesycontrol_pb2',
                 # These are required for the windows package to work
                 'pyqtgraph.console.template_pyside2',
                 'pyqtgraph.graphicsItems.ViewBox.axisCtrlTemplate_pyside2',
                 'pyqtgraph.graphicsItems.PlotItem.plotConfigTemplate_pyside2',
                 'pyqtgraph.imageview.ImageViewTemplate_pyside2',
                 ],
             runtime_hooks=[],
             excludes=[
                 'pyqtgraph.opengl',
                 ],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

a_mc_script = Analysis(['mesycontrol_script.py'],
             pathex=[],
             binaries=binaries,
             datas=[],
             # pyinstaller does not evaulate __all__ nor do the star imports work
             hiddenimports=[
                 'google.protobuf.text_format',
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
                 'mesycontrol.mesycontrol_pb2',
                 # These are required for the windows package to work
                 'pyqtgraph.console.template_pyside2',
                 'pyqtgraph.graphicsItems.ViewBox.axisCtrlTemplate_pyside2',
                 'pyqtgraph.graphicsItems.PlotItem.plotConfigTemplate_pyside2',
                 'pyqtgraph.imageview.ImageViewTemplate_pyside2',
                 ],
             runtime_hooks=[],
             excludes=[
                 'pyqtgraph.opengl',
                 ],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

# Do not package fontconfig. It will fail to load the fonts.conf file on newer
# systems. Instead at runtime the system libfontconfig must be loaded. This
# seems to work for now.
# Credit to: https://stackoverflow.com/a/17595149/17562886
excluded_libs = TOC([
    ('libfontconfig.so.1', None, None),
    ('libfreetype.so.6', None, None),
    #('libharf', None, None),
])

a_mc_gui.binaries = a_mc_gui.binaries - excluded_libs
a_mc_script.binaries = a_mc_script.binaries - excluded_libs

# https://pyinstaller.org/en/stable/spec-files.html#multipackage-bundles
MERGE((a_mc_gui, 'mesycontrol_gui', 'mesycontrol_gui'), (a_mc_script, 'mesycontrol_script_runner', 'mesycontrol_script_runner'))

#print(a.binaries)

pyz_mc_gui = PYZ(a_mc_gui.pure, a_mc_gui.zipped_data, cipher=block_cipher)
pyz_mc_script = PYZ(a_mc_script.pure, a_mc_script.zipped_data, cipher=block_cipher)

exe_mc_gui = EXE(pyz_mc_gui,
          a_mc_gui.scripts,
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

exe_mc_script = EXE(pyz_mc_script,
          a_mc_script.scripts,
          [],
          exclude_binaries=True,
          name='mesycontrol_script_runner',
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

coll = COLLECT(exe_mc_gui,
               a_mc_gui.binaries,
               a_mc_gui.zipfiles,
               a_mc_gui.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='mesycontrol_gui')

coll = COLLECT(exe_mc_script,
               a_mc_script.binaries,
               a_mc_script.zipfiles,
               a_mc_script.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='mesycontrol_script_runner')

# vim:ft=python
