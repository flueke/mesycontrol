.. mesycontrol documentation master file, created by
   sphinx-quickstart on Mon Sep 15 09:48:17 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. toctree::

*mesycontrol* documentation
===========================

Introduction
------------
*mesycontrol* is a remote control solution for detector readout systems by
mesytec. *mesycontrol* makes use of the mesytec RC bus controllers (MRC-1/MRCC)
to communicate with the actual devices. For user interaction a GUI application
is provided.

Features
^^^^^^^^
* MRC-1/MRCC connectivity via USB, serial port and network.
* Client-server architecture using plain TCP as the transport. This enables the
  graphical frontend to run and operate on machines without direct access to
  the mesytec hardware.
* Storing and loading of single device configurations and complete setups
  (multiple devices and multiple MRCs).
* Tabular view/editing of device memory.
* Custom GUIs for MHV-4, MSCF-16, STM-16 and MCFD-16.
* Polling of frequently changing parameters (e.g. voltage or current)
* Cross-platform: both client and server run on Linux and Windows
* Offline editing: device configurations can be created/edited without access
  to the hardware.

Installation and dependencies
-----------------------------
Linux
^^^^^
*mesycontrol* requires the Qt libraries >= 4.8 to be installed on your system.
Also be sure to pick the right archive for your distribution and architecture
as trying to run the 32 bit version of the software on a 64 bit linux
installation will most likely result in errors about missing libraries. 

The installation itself is simple: unpack the tar.bz2 archive and execute the
*mesycontrol_gui* binary to get started:::

  $ tar xf mesycontrol-0.5.tar.bz2
  $ ./mesycontrol-0.5/bin/mesycontrol_gui

Note: so far *mesycontrol* has only been tested on Debian Wheezy, Ubuntu 12.04
and OpenSUSE 12.1 but it should work on other distributions and versions as
long as the C++ and Qt libraries stay binary compatible.

Windows
^^^^^^^
*mesycontrol* does not require any additional dependencies on Windows. Running
the supplied installer and following the wizard should correctly install the
software and create a start menu entry for the GUI application.

Architecture Overview
---------------------
.. figure:: architecture.png

   mesycontrol architecture

*mesycontrol* is divided into two parts: *mesycontrol_server* handling MRC
connectivity and communication, and the client part (*mesycontrol_gui*)
connecting to running server processes via TCP.

The GUI client will transparently spawn its own server process if the user
requests a MRC connection via serial port or USB.

In case the client PC does not have a direct (USB, Serial) connection to an
MRC-1/MRCC the server can be run stand-alone on a machine with direct access to
the hardware. The GUI client then connects via a TCP connection to the remotely
running server process.

The client supports connections to multiple servers and is thus able to control
multiple MRC-1/MRCCs.

Using mesycontrol
-----------------
Concepts and Terms
^^^^^^^^^^^^^^^^^^

* MRC

  A MRC-1 or MRCC mesytec RC bus master. In the GUI each MRC is uniquely
  identified by its connection URL.

  The are three ways to connect to a MRC:

  * Connecting the MRC to a local serial or USB port.
  * Via a serial server which is connected to the MRC.
  * Connecting to a (remotely) running *mesycontrol_server* instance.

* Device

  A mesytec device with support for the mesytec remote control bus. A device is
  identified by its parent MRC, its bus number and its address on the bus. The
  device type is determined by the devices ID code.

* Setup

  A tree of MRC configurations and their child device configs.
  Can be loaded from and saved to file.


GUI overview
^^^^^^^^^^^^
.. figure:: treeview-unlinked.png
   :width: 12cm

   Device tree with **linked_mode** disabled.

The GUI shows hardware and config trees side-by-side. On the left side active
MRC connections and their connected devices are shown. On the right side the
currently opened setup with its MRC and device configurations is displayed.

At startup the two sides will not be linked together. This means hardware and
setup can be separately edited without affecting each other.

Using the *link mode* button in the center of the tree view **linked-mode** can
be activated. In this mode the hardware and setup trees are compared against
each other, differences and conflicts are highlighted and devices missing on
either side are also shown. In linked-mode it is possible to have changes to
device parameters apply to both the hardware and the config side keeping both
trees in sync.

.. figure:: treeview-linked.png
   :width: 12cm

   Device tree with **linked_mode** enabled.

Devices with a red background have conflicting device types (their IDCs do not
match). A green background means hardware and config parameters are equal.
Orange indicates that hardware and config states differ.

Using the arrow buttons on the center bar device state can be copied from
hardware to config and vice-versa. This works for single devices aswell as for
parts of the tree (e.g. apply all device configs of the selected MRC to the
hardware).

Pressing the checkmark icon will (re)read needed parameters from the hardware
and compare them against the configuration.

The two buttons just below the link mode button will open a specialized device
GUI (if one is available) and a tabular view of the devices parameters
respectively.

Device GUIs
^^^^^^^^^^^
Currently there are two types of device GUIs: the device table view which works
for all devices (even devices unknown to the application) and specialized
device GUIs for known devices.

All device GUIs support different display and write modes. In case of the
device table view the following display modes are available: `hardware`,
`config` and `combined` with `combined` displaying both the hardware and the
config columns. The same options are available for the write mode with
`combined` mode writing to the device config first, then to the device
hardware.

Specialized device widgets currently do not support `combined` display mode but
one of `hardware` or `config`. Write mode works the same as for device table
views.

The side of the device tree that is selected, the availability of
hardware/config and the state of **linked_mode** determine the display and
write modes for newly opened device windows. Using two buttons at the top
toolbar both modes can be changed after window creation.

.. figure:: display-and-write-mode-icons.png
  
   Display and write mode icons.

The modes currently in effect are also displayed in the device windows title
bar.

Display and write modes
Table View
Specialized GUIs

Stand-alone server operation
----------------------------
* Binary location:

  * Linux: bin/mesycontrol_server
  * Windows: mesycontrol_server.exe in the installation path

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

.. TODOS
.. =====
.. .. todolist::

.. Indices and tables
.. ==================
.. 
.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`

