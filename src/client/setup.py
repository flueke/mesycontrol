# setuptools script to test installing via pip.

#!/usr/bin/env python3

import os
import sys

from setuptools import setup, find_packages
from setuptools.command.install import install

class InstallWrapper(install):
    def run(self):
        super().run()
        from pyshortcuts import make_shortcut
        make_shortcut(os.path.join(self.install_base, 'Scripts', 'cad_gui.exe'), name="Cad Gui")
        make_shortcut(os.path.join(self.install_base, 'Scripts', 'prod_gui.exe'), name="Prod Gui")

setup(
    name='mesycontrol',
    description='mesytec NIM module control GUI',
    setup_requires=['setuptools_scm', 'pyshortcuts'],
    install_requires=[
        #'importlib-resources',
        'pyshortcuts==1.8.0',
        'PySide2==5.15.2',
        'shiboken2==5.15.2',
        'numpy',
        'pyqtgraph',
        'protobuf',
    ],
    #use_scm_version= {
    #    "root": ".",
    #    "relative_to": __file__
    #},
    packages=['mesycontrol'],
    include_package_data=True,
    package_data={
        #"mesycontrol": ["data/*.dbf"],
    },
    zip_safe=False,
    entry_points = {
        'gui_scripts': [
            'mesycontrol_gui = mesycontrol:mesycontrol_gui_main',
            #'prod_gui = mesycontrol:prod_gui_main'
            ],

        # Note: can use 'console_scripts' here to start the programs from within
        # a windows cmd shell.
        'console_scripts': [
            #'cad_gui_main = mesycontrol:cad_gui_main',
            #'prod_gui_main = mesycontrol:prod_gui_main',
            #'prod_copy_id_table = mesycontrol:prod_copy_id_table_main',
            ],

    },
    #cmdclass = {'install': InstallWrapper}
)