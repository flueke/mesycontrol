#from nose.tools import assert_raises, assert_dict_equal
#from ..device_tableview import *
#from ..hw_model import *
from mesycontrol.device_tableview import *
from mesycontrol.hw_model import *

def test_simple():
    app = QtGui.QApplication([])

    device_model = DeviceModel(bus=0, address=1, idc=17, rc=True)
    for i in range(256):
        device_model.set_parameter(i, i)
    device       = Device(device_model)
    table_model  = DeviceTableModel(device)
    table_view   = DeviceTableView(table_model)

    def on_button_triggered():
        for i in range(256):
            device_model.set_parameter(i, 
                    device_model.get_parameter(i) + 1)

    def on_set_device_button_triggered():
        table_model.device = device

    button1 = QtGui.QPushButton("set parameters", clicked=on_button_triggered)
    button2 = QtGui.QPushButton("set device", clicked=on_set_device_button_triggered)

    layout = QtGui.QHBoxLayout()
    layout.addWidget(table_view)
    layout.addWidget(button1)
    layout.addWidget(button2)

    w = QtGui.QWidget()
    w.setLayout(layout)
    w.show()

    return app.exec_()

if __name__ == "__main__":
    test_simple()
