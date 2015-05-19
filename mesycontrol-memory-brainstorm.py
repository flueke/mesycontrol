# How to make virtual devices work.
# Motivation:
# Offline creation of Setups. GUI widgets should work almost as if connected to
# the hardware. This means set_parameter, read_parameter and probably a couple
# more methods have to be implemented. Special functions like MSCF16 auto_pz
# won't work. Also logic like mult-low < mult-high won't be enforced unless
# some special device specific simulation code is added.
# Changes to the device memory need to end up in a DeviceConfig object instead
# of being sent to the hardware as a request.

# Does the DeviceWidget need to know if it's handling a real or a virtual device?
# Yes as it must be clear if the hardware state or config state are changed!
# This will also enable the widget to disable certain inputs.

# Device Widgets right now work with specific Device subclasses. They expect a
# specific subclass, e.g. MSCF16 with its special methods.

# Starting point: an empty Setup
# Actions:
# * add MRC connection
#   Needs connection params just like the real connection.
#   Check for duplicate connection details.
# * add device to an MRC
#   Needs bus, address, device idc (numeric or known device name).
#   Make the dialog show only unused (bus, address) pairs.
# * remove device from MRC
# * remove MRC
# Might be wanted:
# * modify devices bus and/or address
#   This is a move in the tree. Duplicate (bus, address) pairs should never
#   happen. If forced the existing device will be replaced:
#   remove_existing from tree
#   modify device
#   add modified to tree

class VirtualController(QtCore.QObject):
    """How a virtual MRCController could be implemented.
    The given mrc_model will take the place of both the hardware and the
    applications model of the hardware. This means read requests will return
    the current state of the model, set requests will modify the model.
    """
    def __init__(self, mrc_model, parent=None):
        self.model = mrc_model
        self.model.set_connected()

    def scanbus(self, bus, response_handler=None):
        # Create a ScanbusResponse using the current state of the model.
        # Call the response_handler with that response.
        # => Bus changes will only happen if the model tree gets modified
        # externally.
        pass

    def read_parameter(self, bus, device, address, response_handler=None):
        # Create a response_read message using the models current memory value.
        # Call response_handler
        pass

    def set_parameter(self, bus, device, address, value, response_handler=None):
        # Set the models memory to the new value.
        # This will make the model react to the change and emit
        # parameter_changed. Observers will see the change before the
        # response_handler is called. This is actually the same behaviour the
        # current TCPClient has:
        # message_received and response_received are emitted before the
        # response_handler is called.
        self.model[bus][device][address] = value
        # Create request and response messages.
        req  = Message('request_set', bus=bus, dev=device, par=address, val=value)
        resp = Message('response_set', bus=bus, dev=device, par=address, val=value)
        # Call the response handler
        response_handler(req, resp)

class VirtualConnection(AbstractConnection):
    """Virtual mrc connection implementation.
    This works on the given backend which must conform to the hw_model interface.
    """
    def __init__(self, backend, parent=None):
        super(VirtualConnection, self).__init__(parent)
        self.mrc_backend = backend

    
    def connect(self):
        pass

    def disconnect(self):
        pass

    def is_connected(self):
        return True

    def is_connecting(self):
        return False

    def get_info(self):
        """Returns an info string for this connection."""
        return "virtual connection"

    def get_write_queue_size(self):
        return 0

    def queue_request(self, msg, response_handler=None):
        # Would have to implement the server logic here.
        tn = msg.get_type_name()

        if tn == 'request_read':
            bus, dev, par = msg.bus, msg.dev, msg.par
            val = self.mrc_backend[msg.bus][msg.dev][msg.par]
            resp = Message('response_read', bus=bus, dev=dev, par=par, val=val)
            self._fake_message_sent(msg)
            self._fake_message_received(resp)

        return "some fake request id"

    def _fake_message_received(msg):
        super(VirtualConnection, self)._message_received_handler(msg)

    def cancel_request(self, request_id):
        raise NotImplementedError()

    def cancel_all_requests(self):
        raise NotImplementedError()

# Conclusion so far: virtual connection is horrible to build. Virtual
# controller seems way easier.
# But is this really needed? How about changing the app_model.Device class?
# Take it as an interface, make specific device widgets decorate that
# interface at runtime instead of subclassing. Then implement a
# MesycontrolDevice and a VirtualDevice. The app only has to know that
# interface. Even DeviceConfig can implement the interface.
# Differences remain though:
# * Actions on the real hardware are asynchronous, on virtual hardware they're
#   synchronous.
# * Requests are expensive on the hardware. Care has to be taken to avoid
#   fetching duplicate data. Distinction between read (perform an actual read
#   operation) and get (return a cached value)!
# * Connection states are mostly useless for virtual hardware (unless specific
#   behaviour of certain components is wanted and thus connection states are
#   simulated).
# * Virtual hardware does not enforce parameter limits unless simulation code
#   is added.
# * Models of the hardware are often "incomplete": bus has not been scanned
#   yet, parameter is not yet available, etc...
# * As it is right now Device passes requests down to its MRC via its
#   DeviceController. Models of real hardware need to be connected to an MRC,
#   for models of virtual hardware that's not neccessary. They at least need to
#   be connected to a controller sending network requests.
# * DeviceConfig has attached meta info (name, description), technical info
#   (filename, modified) and extensions (Device.get_extensions).

# XXX
# * Transition from MesycontrolDevice to VirtualDevice to DeviceConfig?
#   => Take attributes (bus, addr, mem) from MesycontrolDevice and set on newly
#      created VirtualDevice.
#       e.g. DeviceConfig.from_device(device) # pass anything having the device interface here
#       Should return a Future as getting params might take time.
#   Meaning no DeviceConfig class anymore.
# * There will most likely be protocol specific behaviour. I.e. can the MRC to read_multi?
#   Protocol handling. Modifications.
# * Root of tree object will differ: can be an MRC, can be a Setup or something else.
# DeviceProfile stuff?! It influences device memory lookups, config writing, config loading, etc.

# Things that would be nice with having a unified interface:
# * Operations on devices/device configs would be implemented once and work for
#   both.
# * 

# Code samples

ctrl = MRCController("/dev/ttyUSB0")
mrc  = MRC()
ctrl.set_mrc(mrc)
mrc.set_ctrl(ctrl)
