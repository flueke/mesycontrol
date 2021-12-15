#!/usr/bin/env python
# -*- coding: utf-8 -*-

import random
import sys

from mesycontrol.qt import Qt
from mesycontrol.qt import QtCore
from mesycontrol.qt import QtGui
from mesycontrol.qt import QtWidgets
from mesycontrol.qt import PySide2

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    centerWidget = QtWidgets.QWidget()
    centerLayout = QtWidgets.QVBoxLayout(centerWidget)

    for i in range(10):
        letterCount = random.randint(0, 10)
        buttonText = f"Button {i}" + "z" * letterCount
        button = QtWidgets.QToolButton()
        button.setText(buttonText)
        button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        centerLayout.addWidget(button)

    centerLayout.addStretch(1)
    centerWidget.setFixedWidth(centerWidget.sizeHint().width())

    leftTree = QtWidgets.QTreeView()
    rightTree = QtWidgets.QTreeView()

    splitter = QtWidgets.QSplitter()
    splitter.addWidget(leftTree)
    splitter.addWidget(centerWidget)
    splitter.addWidget(rightTree)

    splitter.show()

    sys.exit(app.exec_())
