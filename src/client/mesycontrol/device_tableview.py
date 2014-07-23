from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import QModelIndex
from PyQt4.QtCore import Qt
from functools import partial
import weakref

from app_model import Device
from util import TreeNode

column_names     = ('address', 'value', 'name', 'alias', 'config_value', 'set_value', 'config_set')
column_titles    = ('Address', 'Value', 'Name', 'Alias', 'Config Value', 'Set Value', 'Config & Set')

class ParameterNode(TreeNode):
    data_changed = pyqtSignal()

    def __init__(self, device, address, parent):
        super(ParameterNode, self).__init__(device, parent)
        self.address = address
        device.parameter_changed.connect(self._on_parameter_changed)

    def _on_parameter_changed(self, address, old, new):
        if self.address == address:
            self.data_changed.emit()

    def flags(self, column):
        ret = (Qt.ItemIsSelectable | Qt.ItemIsEnabled)

        if column_names[column] in ('name', 'alias', 'config_value', 'set_value', 'config_set'):
            ret |= Qt.ItemIsEditable

        return ret

    def get_value(self):
        return self.ref.model.get_memory().get(self.address, None)

    def get_config(self):
        if self.ref.config is not None:
            return self.ref.config.get_parameter(self.address)
        return None

    def get_description(self):
        if self.ref.description is not None:
            return self.ref.description.get_parameter_by_address(self.address)
        return None

    def data(self, column, role):
        mem_value    = self.get_value()
        param_config = self.get_config()
        param_descr  = self.get_description()
        column_name  = column_names[column]

        if role in (Qt.DisplayRole, Qt.EditRole):
            if column_name == 'address':
                return self.address
            elif column_name == 'value':
                return mem_value
            elif column_name == 'name':
                if role == Qt.DisplayRole:
                    return param_descr.name if param_descr is not None else None
                return param_descr.name if param_descr is not None else str()
            elif column_name == 'alias':
                if role == Qt.DisplayRole:
                    return param_config.alias if param_config is not None else None
                return param_config.alias if param_config is not None else str()
            elif column_name == 'config_value':
                if role == Qt.DisplayRole:
                    return param_config.value if param_config is not None else None
                return param_config.value if param_config is not None else int()
        return None
            

    def set_data(self, column, value, role):
        print "set_data", column, value, role
        if role == Qt.EditRole:
            return True
        return False

    def context_menu(self):
        return None

# table model
class DeviceTableModel(QtCore.QAbstractTableModel):
    def __init__(self, device, parent=None):
        super(DeviceTableModel, self).__init__(parent)
        self.root   = TreeNode(None)
        self.device = device

    def set_device(self, device):
        self.beginResetModel()

        for parameter_node in self.root.children:
            parameter_node.setParent(None)

        self.root.children = list()

        for i in range(256):
            parameter_node = ParameterNode(device, i, self.root)
            parameter_node.data_changed.connect(partial(self._on_parameter_node_changed, address=i))
            self.root.children.append(parameter_node)

        self._device = weakref.ref(device)

        self.endResetModel()

    def get_device(self):
        return self._device()

    device = pyqtProperty(Device, get_device, set_device)

    def _on_parameter_node_changed(self, address):
        idx1 = self.createIndex(address, 0, self.root)
        idx2 = self.createIndex(address, self.columnCount(), self.root)
        self.dataChanged.emit(idx1, idx2)


    # ===== QAbstractItemModel implementation =====
    def columnCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(column_names)
        return 0

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return len(self.root.children)
        return 0

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            try:
                return column_titles[section]
            except IndexError:
                return None
        elif orientation == Qt.Vertical and role == Qt.DisplayRole:
            return section
        return None

    def flags(self, idx):
        ret = None
        if idx.isValid():
            try:
                ret = self.root.children[idx.row()].flags(idx.column())
            except NotImplementedError:
                pass
        return ret if ret is not None else super(DeviceTableModel, self).flags(idx)

    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid():
            return None
        return self.root.children[idx.row()].data(idx.column(), role)

    def setData(self, idx, value, role = Qt.EditRole):
        ret = False
        if idx.isValid():
            try:
                ret = self.root.children[idx.row()].set_data(idx.column(), value, role)
            except NotImplementedError:
                pass
        if ret:
            self.dataChanged.emit(
                    self.index(idx.row(), 0),
                    self.index(idx.row(), self.columnCount()))
        return ret

class DeviceTableView(QtGui.QTableView):
    def __init__(self, model, parent=None):
        super(DeviceTableView, self).__init__(parent)
        self.table_model = model
        self.sort_model  = QtGui.QSortFilterProxyModel(self)
        self.sort_model.setSourceModel(model)
        self.sort_model.setDynamicSortFilter(True)
        self.setModel(self.sort_model)

        model.modelReset.connect(self.resizeColumnsToContents)
        model.modelReset.connect(self.resizeRowsToContents)

        self.verticalHeader().hide()
        self.horizontalHeader().setMovable(True)
        self.sortByColumn(0, Qt.AscendingOrder)
        self.setSortingEnabled(True)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.doubleClicked.connect(self._on_item_doubleclicked)

    def _on_item_doubleclicked(self, idx):
        idx = self.sort_model.mapToSource(idx)
        print "click on", idx.row(), idx.column(), idx.internalPointer()
        if self.model().flags(idx) & Qt.ItemIsEditable:
            print 'editable'