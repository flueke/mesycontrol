#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import pyqtSlot
from qt import Qt
from qt import QtCore
from qt import QtGui

from mc_treeview import MCTreeView
from util import make_icon
import gui_util
import log_view
import util

class MCMdiArea(QtGui.QMdiArea):
    def __init__(self, parent=None):
        super(MCMdiArea, self).__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

class MainWindow(QtGui.QMainWindow):
    def __init__(self, context, parent=None):
        super(MainWindow, self).__init__(parent)
        self.log = util.make_logging_source_adapter(__name__, self)
        self.context = context
        util.loadUi(":/ui/mainwin.ui", self)
        self.setWindowIcon(make_icon(":/window-icon.png"))

        # Treeview
        self.treeview = MCTreeView(app_registry=context.app_registry,
                device_registry=context.device_registry)

        dw_tree = QtGui.QDockWidget("Device tree", self)
        dw_tree.setObjectName("dw_treeview")
        dw_tree.setWidget(self.treeview)
        dw_tree.setFeatures(QtGui.QDockWidget.DockWidgetMovable | QtGui.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dw_tree)

        # Log view
        self.logview = log_view.LogView(parent=self)
        dw_logview = QtGui.QDockWidget("Application Log", self)
        dw_logview.setObjectName("dw_logview")
        dw_logview.setWidget(self.logview)
        dw_logview.setFeatures(QtGui.QDockWidget.DockWidgetMovable | QtGui.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dw_logview)

        # Note: do not call restore_settings() here. It needs to be called
        # after self.show() to work properly!

    def store_settings(self):
        settings = self.context.make_qsettings()

        settings.beginGroup("MainWindow")

        try:
            settings.setValue("size",       self.size());
            settings.setValue("pos",        self.pos());
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
            self.resize(settings.value("size", QtCore.QSize(1024, 768)).toSize())
            self.move(settings.value("pos", QtCore.QPoint(0, 0)).toPoint())
            self.restoreGeometry(settings.value("geometry").toByteArray())
            self.restoreState(settings.value("state").toByteArray())
        finally:
            settings.endGroup()

        self.treeview.splitter.restoreState(
                settings.value("MCTreeView/state").toByteArray())

    @pyqtSlot()
    def on_actionAbout_triggered(self):
        try:
            from . import mc_version
            version = mc_version.version
        except ImportError:
            version = "devel version"

        d = QtGui.QDialog(self)
        d.setWindowTitle("About mesycontrol")

        license = QtGui.QTextBrowser(parent=d)
        license.setWindowFlags(Qt.Window)
        license.setWindowTitle("mesycontrol license")
        license.setText("")

        try:
            f = QtCore.QFile(":/gpl.txt")
            if not f.open(QtCore.QIODevice.ReadOnly | QtCore.QIODevice.Text):
                return
            license.setText(QtCore.QString(f.readAll()))
        finally:
            f.close()

        l = QtGui.QVBoxLayout(d)

        logo = QtGui.QLabel()
        logo.setPixmap(QtGui.QPixmap(":/mesytec-logo.png"
            ).scaledToWidth(300, Qt.SmoothTransformation))
        l.addWidget(logo)

        t = "mesycontrol - %s" % version
        label = QtGui.QLabel(t)
        font  = label.font()
        font.setPointSize(15)
        font.setBold(True)
        label.setFont(font)
        l.addWidget(label)

        l.addWidget(QtGui.QLabel("Remote control for mesytec devices."))
        l.addWidget(QtGui.QLabel(QtCore.QString.fromUtf8("© 2014-2015 mesytec GmbH & Co. KG")))

        t = '<a href="mailto:info@mesytec.com">info@mesytec.com</a> - <a href="http://www.mesytec.com">www.mesytec.com</a>'
        label = QtGui.QLabel(t)
        label.setOpenExternalLinks(True)
        l.addWidget(label)

        l.addSpacing(20)

        bl = QtGui.QHBoxLayout()

        def license_button_clicked():
            sz = license.size()
            sz = sz.expandedTo(QtCore.QSize(500, 300))
            license.resize(sz)
            license.show()
            license.raise_()

        b = QtGui.QPushButton("&License", clicked=license_button_clicked)
        bl.addWidget(b)

        b = QtGui.QPushButton("&Close", clicked=d.close)
        b.setAutoDefault(True)
        b.setDefault(True)
        bl.addWidget(b)

        l.addLayout(bl)

        for item in (l.itemAt(i) for i in range(l.count())):
            item.setAlignment(Qt.AlignHCenter)

            w = item.widget()

            if isinstance(w, QtGui.QLabel):
                w.setTextInteractionFlags(Qt.TextBrowserInteraction)

        d.exec_()

    @pyqtSlot()
    def on_actionAbout_Qt_triggered(self):
        QtGui.QApplication.instance().aboutQt()

    def closeEvent(self, event):
        self.store_settings()
        super(MainWindow, self).closeEvent(event)

