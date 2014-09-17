.. mesycontrol documentation master file, created by
   sphinx-quickstart on Mon Sep 15 09:48:17 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

mesycontrol documentation
=========================

Introduction
------------
mesycontrol is a remote control solution for detector readout systems by
mesytec. mesycontrol makes use of the mesytec RC bus controllers (MRC-1/MRCC)
to communicate with the actual devices. For user interaction a GUI application
is provided. Automated device control can be achieved via scripting support
built into the application.

Features
^^^^^^^^
* MRC-1/MRCC connectivity via USB, serial port and network
* Client-server architecture using plain TCP as the transport. This enables the
  graphical frontend to run and operate on machines without direct access to
  the mesytec hardware
* Storing and loading of single device configurations and complete setups
  (multiple devices and multiple MRCs)
* Tabular view of the device memory
* Specialized panels for MHV-4 and MSCF-16
* Polling of frequently changing parameters (e.g. voltage or current)
* Scripting support (Python) to automate device control
* Silent mode to temporarily disable any mesytec eventbus communication
* Cross-platform: both, client and server, work on Linux and Windows

Installation and dependencies
-----------------------------
Linux
^^^^^
mesycontrol requires the Qt libraries >= 4.8 to be installed on your system.
Also be sure to pick the right archive for your distribution and architecture
as trying to run the 32 bit version of the software on a 64 bit linux
installation will most likely result in errors about missing libraries. 

The installation itself is simple: unpack the tar.bz2 archive and execute the
*mesycontrol_gui* binary to get started:::

  $ tar xf mesycontrol-0.3-36-g75d9fdf.tar.bz2
  $ ./mesycontrol-0.3-36-g75d9fdf/bin/mesycontrol_gui

Note: so far mesycontrol has only been tested on Debian Wheezy, Ubuntu 14.04
and OpenSUSE 12.1 but it should work on other distributions and versions as
long as the C++ and Qt libraries stay binary compatible.

Windows
^^^^^^^
mesycontrol does not require any additional dependencies on Windows. Running
the supplied installer and following the wizard should correctly install the
software and create a start menu entry for the GUI application.

Architecture Overview
---------------------
.. graphviz:: architecture.dot

mesycontrol is divided into two parts, the server handling MRC connectivity and
communication, and the client part connecting to running server processes via
TCP.

Using the mesycontrol GUI
-------------------------
* empty setup at startup
* add MRCs to the setup via the the menu: **File -> Connect**
* Connection types

  * Serial: the MRC is directly plugged into your computer (either via USB or
    using a real COM port). Available serial ports should be auto detected.
    Additionaly different serial port names can be added by typing in the
    *Serial Port* drop down box.
  * TCP: the MRC is located at a remote site and connected to either a PC or to
    a serial server device. Specify hostname/IP address and port to establish a
    connection.
  * Mesycontrol: a mesycontrol server process is running stand-alone on a
    network reachable machine.

* MRC and device specific actions can be performed via context menu in the
  setup tree view (right click to open the context menu). Actions include:
  scanbus, disconnect, remove MRC from setup, open a device view, save/load
  device config to/from file.
* To save the complete setup to disk use the **File -> Save Setup** menu entry.
* Loading a setup is achieved via **File -> Load Setup**.
  Loading a setup will connect to all MRCs contained in the setup file and will
  load all device configs onto the devices. In case of missing devices or
  devices not matching the device IDC given in the setup an error is reported
  and the corresponding device is highlighted in the setup tree view.

Device control
^^^^^^^^^^^^^^
* device table view
* device profiles
* specialized device panels
* unsupported devices

Stand-alone server operation
----------------------------
* binary location:

  * linux: bin/mesycontrol_server
  * windows: mesycontrol_server.exe in the installation path

* Handles all MRC communication
* Opens a listening socket and waits for mesycontrol clients to connect
* An overview of all options is available by running::

  $ ./mesycontrol_server --help

* Common use cases:

  * Using a local serial port and listening on all network interfaces:::

      $ ./mesycontrol_server --mrc-serial-port=/dev/ttyUSB0

  * Local serial port as above but limit the listening socket to a certain IP
    address and using a different listening port:::

      $ ./mesycontrol_server --mrc-serial-port=/dev/ttyUSB0 \
        --listen-address=192.168.168.202 --listen-port=23023

  * Connection to a serial server:::

      $ ./mesycontrol_server --mrc-host=example.com --mrc-port=42000

* To stop a running server instance hit *CTRL-C* in the terminal or send the
  termination signal to the process (e.g. via the *kill* command)

Scripting
---------

.. .. automodule:: mesycontrol.app_model
   :members:
   :undoc-members:
   :special-members:

mesycontrol protocol
--------------------

API documentation
-----------------
.. toctree::
   :maxdepth: 2

   client
   server


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

