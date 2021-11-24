#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mesycontrol - Remote control for mesytec devices.
# Copyright (C) 2015-2016 mesytec GmbH & Co. KG <info@mesytec.com>
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

from mesycontrol.qt import Signal
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui
from mesycontrol.qt import QtWidgets
import weakref

class UIFlasher(QtCore.QObject):
    def __init__(self, widget, flashcount=10, interval_ms=500, autostart=False, parent=None):
        super(UIFlasher, self).__init__(parent)
        self.flashcount = flashcount
        self.interval = interval_ms
        self.timer = QtCore.QTimer(self, timeout=self._do_flash)
        self.flash_on = False
        self.widget = None
        self.set_widget(widget, autostart)

    def start(self):
        self._current_flashcount = self.flashcount
        self.timer.start(self.interval)
        self._do_flash()

    def stop(self):
        self.timer.stop()
        if self.flash_on and self.widget and self.widget():
            self.widget().setStyleSheet('')

    def set_widget(self, widget, autostart=True):
        if self.widget is not None and self.widget() is widget and autostart:
            if not self.timer.isActive():
                self.start()
            return

        self.stop()
        self.widget = weakref.ref(widget)

        if autostart:
            self.start()

    def _do_flash(self):
        if self._current_flashcount <= 0 or not self.widget or not self.widget():
            return

        style = '' if self.flash_on else 'background: yellow;'
        self.widget().setStyleSheet(style)

        if self.flash_on:
            self._current_flashcount -= 1

        self.flash_on = not self.flash_on

        if self._current_flashcount <= 0:
            self.stop()

class TutorialTextBrowser(QtWidgets.QTextBrowser):
    href_hover = Signal(str)

    def __init__(self, parent=None, **kwargs):
        super(TutorialTextBrowser, self).__init__(parent=parent, **kwargs)
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event):
        pos = event.pos()
        cursor = self.cursorForPosition(pos)
        cursor.select(QtGui.QTextCursor.WordUnderCursor)
        fmt = cursor.charFormat()

        self.href_hover.emit(str(fmt.anchorHref()) if fmt.isAnchor() else str())

        super(TutorialTextBrowser, self).mouseMoveEvent(event)

class TutorialWidget(QtWidgets.QWidget):
    def __init__(self, gui_app, parent=None):
        super(TutorialWidget, self).__init__(parent)
        self.gui_app = gui_app

        #self.setStyleSheet('background: lightyellow;')

        self.text_doc = QtGui.QTextDocument(self)

        f = QtCore.QFile(":/quickstart.html")
        if f.open(QtCore.QIODevice.ReadOnly):
            s = QtCore.QTextStream(f)
            html = s.readAll()
        else:
            html = "quickstart.html not found!"

        self.text_doc.setHtml(html)

        self.text_browser = TutorialTextBrowser(openLinks=False)
        self.text_browser.setDocument(self.text_doc)
        self.text_browser.href_hover.connect(self._on_href_hover)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_browser)

        self.flasher = UIFlasher(widget=self)

    def _on_href_hover(self, href):
        if not len(href):
            self.flasher.stop()
            return

        scheme, name = str(href).split('://')

        if scheme == 'flash-action':
            action = self.gui_app.actions[name]
            widget = action.associatedWidgets()[-1]
            self.flasher.set_widget(widget)

        elif scheme == 'flash-widget':
            widget = self.gui_app.mainwindow.findChild(QtGui.QWidget, name)
            self.flasher.set_widget(widget)
