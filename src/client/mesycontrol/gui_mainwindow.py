#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2021 mesytec GmbH & Co. KG <info@mesytec.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

__author__ = 'Florian Lüke'
__email__  = 'f.lueke@mesytec.com'

from mesycontrol.qt import Slot
from mesycontrol.qt import Qt
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui
from mesycontrol.qt import QtWidgets
from mesycontrol.qt import PySide2
import platform

from mesycontrol.mc_treeview import MCTreeView
from mesycontrol.util import make_icon
import mesycontrol.gui_util as gui_util
import mesycontrol.log_view as log_view
import mesycontrol.util as util

class MCMdiArea(QtWidgets.QMdiArea):
    def __init__(self, parent=None):
        super(MCMdiArea, self).__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, context, parent=None):
        super(MainWindow, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.context = context
        self.mdiArea = MCMdiArea()
        self.toolbar = self.addToolBar("toolbar")
        self.toolbar.setObjectName("toolbar")
        self.setWindowTitle("mesycontrol")
        self.setWindowIcon(make_icon(":/window-icon.png"))

        self.mdiArea.setLayout(QtWidgets.QGridLayout())
        self.setCentralWidget(self.mdiArea)

        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)

        self.actionQuickstart = QtWidgets.QAction("Quickstart")
        self.actionQuickstart.setShortcut("F1")

        self.menu_file = QtWidgets.QMenu("&File")
        self.menu_window = QtWidgets.QMenu("&Window")
        self.menu_help = QtWidgets.QMenu("&Help")

        self.menu_help.addAction(self.actionQuickstart)
        self.menu_help.addSeparator()
        self.menu_help.addAction("&About", self.on_actionAbout_triggered)
        self.menu_help.addAction("About &Qt", self.on_actionAbout_Qt_triggered)

        self.menu_bar = self.menuBar()
        self.menu_bar.addMenu(self.menu_file)
        self.menu_bar.addMenu(self.menu_help)


        # Treeview
        self.treeview = MCTreeView(app_registry=context.app_registry,
                device_registry=context.device_registry)

        dw_tree = QtWidgets.QDockWidget("Device tree", self)
        dw_tree.setObjectName("dw_treeview")
        dw_tree.setWidget(self.treeview)
        dw_tree.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dw_tree)

        # Log view
        self.logview = log_view.LogView(parent=self)
        dw_logview = QtWidgets.QDockWidget("Application Log", self)
        dw_logview.setObjectName("dw_logview")
        dw_logview.setWidget(self.logview)
        dw_logview.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dw_logview)

        # Note: do not call restore_settings() here. It needs to be called
        # after self.show() to work properly!

    def store_settings(self):
        settings = self.context.make_qsettings()

        settings.beginGroup("MainWindow")

        try:
            settings.setValue("size",       self.size().toTuple());
            settings.setValue("pos",        self.pos().toTuple());
            settings.setValue("geometry",   self.saveGeometry());
            settings.setValue("state",      self.saveState());
        finally:
            settings.endGroup()

        window_list = self.mdiArea.subWindowList()

        for window in window_list:
            gui_util.store_subwindow_state(window, settings)

        settings.setValue("MCTreeView/state", self.treeview.splitter.saveState())

    def restore_settings(self):
        settings = self.context.make_qsettings()


        settings.beginGroup("MainWindow")
        try:
            self.resize(*settings.value("size", (1024, 768)))
            self.move(*settings.value("pos", (0, 0)))
            self.restoreGeometry(settings.value("geometry"))
            self.restoreState(settings.value("state"))
        except TypeError:
            # Settings generated by the old pyqt4 version of mesycontrol are
            # not compatible with the PySide2 generated files.
            pass
        finally:
            settings.endGroup()

        self.treeview.splitter.restoreState(
                settings.value("MCTreeView/state"))

    @Slot()
    def on_actionAbout_triggered(self):
        try:
            from . import mc_version
            version = mc_version.version
        except ImportError:
            version = "devel version"

        d = QtWidgets.QDialog(self)
        d.setWindowTitle("About mesycontrol")

        license = QtWidgets.QTextBrowser(parent=d)
        license.setWindowFlags(Qt.Window)
        license.setWindowTitle("mesycontrol license")
        license.setText("")

        try:
            f = QtCore.QFile(":/gpl-notice.txt")
            if not f.open(QtCore.QIODevice.ReadOnly | QtCore.QIODevice.Text):
                return
            license.setPlainText(str(f.readAll(), 'utf-8'))
        finally:
            f.close()

        l = QtWidgets.QVBoxLayout(d)

        logo = QtWidgets.QLabel()
        logo.setPixmap(QtGui.QPixmap(":/mesytec-logo.png"
            ).scaledToWidth(300, Qt.SmoothTransformation))
        l.addWidget(logo)

        t = "mesycontrol - %s" % version
        label = QtWidgets.QLabel(t)
        font  = label.font()
        font.setPointSize(15)
        font.setBold(True)
        label.setFont(font)
        l.addWidget(label)

        l.addWidget(QtWidgets.QLabel("Remote control for mesytec devices."))
        l.addWidget(QtWidgets.QLabel("© 2014-2021 mesytec GmbH & Co. KG"))

        t = '<a href="mailto:info@mesytec.com">info@mesytec.com</a> - <a href="http://www.mesytec.com">www.mesytec.com</a>'
        label = QtWidgets.QLabel(t)
        label.setOpenExternalLinks(True)
        l.addWidget(label)

        t = 'Running on Python %s using PySide2 %s with Qt %s.' % (
                platform.python_version(), PySide2.__version__, PySide2.QtCore.__version__)
        l.addWidget(QtWidgets.QLabel(t))

        l.addSpacing(20)

        bl = QtWidgets.QHBoxLayout()

        def license_button_clicked():
            sz = license.size()
            sz = sz.expandedTo(QtCore.QSize(500, 300))
            license.resize(sz)
            license.show()
            license.raise_()

        b = QtWidgets.QPushButton("&License", clicked=license_button_clicked)
        bl.addWidget(b)

        b = QtWidgets.QPushButton("&Close", clicked=d.close)
        b.setAutoDefault(True)
        b.setDefault(True)
        bl.addWidget(b)

        l.addLayout(bl)

        for item in (l.itemAt(i) for i in range(l.count())):
            item.setAlignment(Qt.AlignHCenter)

            w = item.widget()

            if isinstance(w, QtWidgets.QLabel):
                w.setTextInteractionFlags(Qt.TextBrowserInteraction)

        d.exec_()

    @Slot()
    def on_actionAbout_Qt_triggered(self):
        QtWidgets.QApplication.instance().aboutQt()

    def closeEvent(self, event):
        self.store_settings()
        super(MainWindow, self).closeEvent(event)

