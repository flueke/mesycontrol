from mesycontrol.hw_model import *

def test_scanbus_creates_devices():
    scanbus_data = [(0, 0) for i in range(16)]
    scanbus_data[0] = (17, 1)
    scanbus_data[2] = (21, 0)

    mrc = MRCModel()

    for i in range(16):
        assert not mrc.has_device(0, i)

    mrc.set_scanbus_data(0, scanbus_data)

    for i in range(16):
        if scanbus_data[i][0] > 0:
            assert mrc.has_device(0, i)
            assert mrc.get_device(0, i).idc == scanbus_data[i][0]
            assert mrc.get_device(0, i).mrc == mrc
        else:
            assert not mrc.has_device(0, i)

