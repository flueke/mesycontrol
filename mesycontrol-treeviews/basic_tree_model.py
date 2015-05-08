#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Florian Lüke <florianlueke@gmx.net>

from qt import QtCore
from qt import Qt

QModelIndex = QtCore.QModelIndex

import weakref

class BasicTreeModel(QtCore.QAbstractItemModel):
    def __init__(self, parent=None):
        super(BasicTreeModel, self).__init__(parent)
        self.root = BasicTreeNode()
        self.root.model = self

    def index(self, row, col, parent=QModelIndex()):
        try:
            root = parent.internalPointer() if parent.isValid() else self.root
            return self.createIndex(row, col, root.children[row])
        except IndexError:
            return QModelIndex()

    def parent(self, idx):
        node = idx.internalPointer() if idx.isValid() else None

        if node is None or node.parent is None:
            return QModelIndex()

        return self.createIndex(node.parent.row, 0, node.parent)

    def rowCount(self, parent=QModelIndex()):
        node = parent.internalPointer() if parent.isValid() else self.root
        return len(node.children)

    def flags(self, idx):
        if idx.isValid():
            try:
                return idx.internalPointer().flags(idx.column())
            except NotImplementedError:
                pass
        return super(BasicTreeModel, self).flags(idx)

    def setData(self, idx, value, role = Qt.EditRole):
        if idx.isValid():
            try:
                if idx.internalPointer().set_data(idx.column(), value, role):
                    self.dataChanged.emit(
                            self.index(idx.row(), 0, idx.parent()),
                            self.index(idx.row(), self.columnCount(idx.parent()), idx.parent()))
            except NotImplementedError:
                pass

        return super(BasicTreeModel, self).setData(idx, value, role)

    def add_node(self, node, parent_node, row):
        parent_idx  = self.createIndex(parent_node.row, 0, parent_node)
        self.beginInsertRows(parent_idx, row, row)
        parent_node.children.insert(row, node)
        node.parent = parent_node
        self.endInsertRows()

    def remove_node(self, node):
        parent_idx = self.createIndex(node.parent.row, 0, node.parent)
        self.beginRemoveRows(parent_idx, node.row, node.row)
        node.parent.children.remove(node)
        node.parent = None
        self.endRemoveRows()
        
    def notify_data_changed(self, node, col1=None, col2=None):
        if col1 is None: col1 = 0
        if col2 is None: col2 = self.columnCount()

        idx1 = self.createIndex(node.row, col1, node)
        idx2 = self.createIndex(node.row, col2, node)
        self.dataChanged.emit(idx1, idx2)

class BasicTreeNode(object):
    """Support class for implementing the nodes of a Qt tree model."""
    def __init__(self, ref=None, parent=None):
        super(BasicTreeNode, self).__init__()
        self._model     = None
        self._parent    = None
        self.ref        = ref
        self.parent     = parent
        self.children   = list()

    def get_ref(self):
        return self._ref() if self.has_ref() else None

    def set_ref(self, ref):
        self._ref = weakref.ref(ref) if ref is not None else None
        if self.model is not None:
            self.model.notify_data_changed(self, 0, self.model.columnCount())

    def has_ref(self):
        return self._ref is not None

    def get_parent(self):
        return self._parent() if self._parent is not None else None

    def set_parent(self, parent):
        self._parent = weakref.ref(parent) if parent is not None else None

    def get_row(self):
        if self.parent is not None:
            return self.parent.children.index(self)
        return 0

    def get_model(self):
        """
        Get this nodes model. If no model is set for this node return the
        parent nodes model. Return None if no model is set for the node
        hierarchy.
        """
        if self._model is not None:
            return self._model()

        if self.parent is not None:
            return self.parent.model

        return None

    def set_model(self, model):
        self._model = weakref.ref(model) if model is not None else None

    def find_node_by_ref(self, ref):
        if self.ref is ref:
            return self

        for c in self.children:
            ret = c.find_node_by_ref(ref)
            if ret is not None:
                return ret

        return None

    def append_child(self, child):
        self.children.append(child)
        child.parent = self

    def flags(self, column):
        raise NotImplementedError()

    def data(self, column, role):
        raise NotImplementedError()

    def set_data(self, column, value, role):
        raise NotImplementedError()

    ref     = property(get_ref, set_ref)
    parent  = property(get_parent, set_parent)
    row     = property(get_row)
    model   = property(get_model, set_model)
