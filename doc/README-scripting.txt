==== mesycontrol script environment and functions =====

* Minimal python script:
    # Import the mesycontrol scripting functions
    from mesycontrol.script import *

    with get_script_context() as ctx:
        # do stuff here...
        connection = ctx.make_connection(url='/dev/ttyUSB0@115200')
        connection.connect()
        mrc = connection.mrc
        device = mrc[0][1] # Get device on bus 0 with address 1
        value = device[32] # Read address 32
        print "Value is %d" % value

* Script context:
    Use get_script_context() to initialize and retrieve the current context.
    Using the context inside a 'with' statement will ensure that all resources
    are properly closed and released on program exit.

    Currently the script context contains only one method and one attribute:

    - Context.make_connection() is used to establish a MRC connection.
      It takes a variable number of keyword arguments:
      'url': supports '<serial_port>@<baud_rate>', '<host>:<port>' and
        'mesycontrol://<host>:<port>' for serial, tcp and direct
        mesycontrol_server connections.

      'serial_port' and 'baud_rate': create a connection using the given
      serial_port and baud_rate. Same as using 'url' with a string like
      '<serial_port>@<baud_rate>'

      'host' and 'port': creates a TCP connection to an MRC listening on the
      given host and port. Same as using '<host>:<port>' as the 'url'
      argument.

      'mesycontrol_host' and 'mesycontrol_port': creates a direct connection
      to a mesycontrol_server listening on the given host and port.

      The return value of make_connection() is a ConnectionWrapper instance.
      Use ConnectionWrapper.connect() to establish the connection and
      ConnectionWrapper.mrc to get access to the MRC.

      See mrc_connection.factory() for more details about the keyword
      arguments supported by make_connection().

    - Context.app_model
      Reference to the global ApplicationModel instance. Contains a list of
      mrc_connections and loaded device_descriptions.
      Note: the app_model does contain MRCConnection instances, not
      ConnectionWrapper instances. This means you have to manually wrap MRCs
      if obtained from the app_model:
      my_conn     = ctx.app_model.mrc_connections[0]
      mrc_model   = my_conn.mrc_model
      mrc_wrapper = MRCWrapper(mrc_model)
      my_device   = mrc_wrapper[1][15] # my_device is a DeviceWrapper. No
                                       # manual wrapping needed.

* MRC and Device wrappers:
  The scripting environment provides wrappers around MRCModel and DeviceModel
  for synchronous access to devices and parameters.

  - MRCWrapper wraps an MRCModel instance. It supports indexing to retrieve
    connected devices:
    my_device = mrc[0][1]  # get the device on bus 0 with address 1

    my_bus    = mrc[0]     # bus proxy which can later be indexed further to
    my_device = my_bus[1]  # retrieve a device

    If no device is connected or an index is out of range an exception will be
    thrown.

    Access to other attributes is passed to the wrapped MRCModel instance.

  - DeviceWrapper wraps a DeviceModel instance. It supports blocking reads and
    writes of parameters and setting the RC status.

    assert my_device.idc == 17     # Read the device identifier code
    some_value    = my_device[32]  # Read parameter 32 from device memory
    my_device[32] = some_value+13  # Write parameter 32
    my_device.rc  = True           # Turn RC on

    Errors will be signaled via exceptions. Access to other attributes is
    passed on to the underlying DeviceModel instance.

* Scripting functions and Command objects
  A couple of functions and Command objects are imported into the global namespace:

  - Sleep(sleep_duration_ms)
    Delays the script for the given duration.

  - Scanbus(mrc, bus)
    Manually rescan a bus.

  - SetParameter(dev, addr, value)
    Same as dev[addr] = value

  - ReadParameter(dev, addr)
    Same as value = dev[addr]

  - SetRc(dev, on_off)
    Same as dev.rc = on_off

  - AcquireWriteAccess(mrc, force=False) and ReleaseWriteAccess(mrc)
    Acquire and release write access. Useful if multiple clients are connected
    to a single mesycontrol_server and the script requires write access.

  - SetupLoader(config)
    Compound command loading the complete setup contained in the given Config.

  - SetupBuilder()
    Used to create setups. Individual devices can be added via add_device(),
    all devices connected to an MRC can be added via add_mrc().

    Example:
    builder = SetupBuilder()
    builder.add_mrc(my_mrc1)
    builder.add_device(my_mrc2[0])
    config  = builder() # The resulting Config object contains all devices
                        # connected to my_mrc1 and the single device from my_mrc2

  - parse_config_file(filename)
    Reads a Config from the given file.

  - write_config_file(config, filename)
    Writes the given Config instance the given file.

  Command objects can perform asynchronous operations in a blocking way using
  a local Qt event loop. Use the exec_() method to block until the command
  finishes, then call get_result() to get the commands result if any.
  The call operator chains the calls to exec_() and get_result():

  read_cmd = ReadParameter(mrc[0][0], 32)
  value    = read_cmd()

  # or shorter using call immediately:
  value    = ReadParameter(mrc[0][0], 32)()

  Compound commands like SetupBuilder and SetupLoader use Qt signals to report
  their progress:
    def print_progress(cur, tot):
        print "Loading setup (step %d/%d)" % (cur, tot)

    setup_loader = setup.SetupLoader(my_cfg)
    # Connect the progress_changed signal to the local print_progress function
    setup_loader.progress_changed.connect(print_progress)
    setup_loader() # Execute the setup loader
