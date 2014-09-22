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

The client will transparently spawn its own server process if the user requests
a MRC connection via serial port or USB.

Concepts
^^^^^^^^
* **MRC configuration**

  Contains name, description, connection information and device configs.

* **Device configuration**

  Contains name, description, IDC, bus number and bus address, RC status and
  parameter values.

* **Device profile**

  A device profile contains information about a specific device class,
  identified by its IDC. The information consists of a device name (e.g.
  MHV-4-800V or MSCF-16) and parameter profiles.

* **Parameter profile**

  A parameter profile holds information about a device memory address.
  Currently the following data can be stored in a parameter profile:

.. tabularcolumns:: | l | l | l | p{10cm} |
..

  +--------------+-------------+-----------------------------------------------------------+
  | **Data**     | **Default** | **Description**                                           |
  +==============+=============+===========================================================+
  | address      |             | The parameters memory address.                            |
  +--------------+-------------+-----------------------------------------------------------+
  | name         | None        | Descriptive name for this parameter (e.g.                 |
  |              |             | *channel1_voltage_write* for the MHV-4 target voltage     |
  |              |             | write address for channel 1).                             |
  +--------------+-------------+-----------------------------------------------------------+
  | poll         | False       | Indicates that this parameter should be polled            |
  |              |             | repeatedly. If polling is actually activated depends on   |
  |              |             | the device view / device panel that's active.             |
  +--------------+-------------+-----------------------------------------------------------+
  | read_only    | False       | The parameter is read-only. Its value will not be stored  |
  |              |             | when writing a device configuration to file.              |
  +--------------+-------------+-----------------------------------------------------------+
  | critical     | False       | This flag marks an address that can have adverse effects  |
  |              |             | when written to the device (e.g. MHV-4 channel enable     |
  |              |             | write address). This flag should be used in combination   |
  |              |             | with the *safe_value* field.                              |
  +--------------+-------------+-----------------------------------------------------------+
  | safe_value   | 0           | A safe value for a parameter marked as *critical*. See    |
  |              |             | below for a description about how *safe_value* and        |
  |              |             | *criticial* influence device config loading.              |
  +--------------+-------------+-----------------------------------------------------------+
  | do_not_store | False       | Marks a parameter that should not be stored in the device |
  |              |             | configuration but is not strictly read-only. Example:     |
  |              |             | MSCF-16 copy function (address 99).                       |
  +--------------+-------------+-----------------------------------------------------------+
  | value_range  | [0..65535]  | Minimum and maximum values this parameter supports.       |
  +--------------+-------------+-----------------------------------------------------------+
  | units        | None        | A list of unit conversions for this parameter. Each unit  |
  |              |             | conversion definition contains a label, a factor and an   |
  |              |             | offset. The latter two are used to convert between raw    |
  |              |             | parameter values and unit values.                         |
  +--------------+-------------+-----------------------------------------------------------+


* A *Setup* contains MRC configurations which in turn contain device configurations
* mesycontrol merges the hardware tree formed by MRC, RC bus and devices with
  the Setup tree. MRCs are matched by their address, devices by their bus
  number, bus address, and device IDC.

.. todo::
   Finish value_range and units implementation. Make unit conversion accessible from the GUI.

   Add an image showing the hardware and config trees and how they're merged.

   Define and explain when and if polling is active.

Using the mesycontrol GUI
-------------------------
.. todo::
   Complete sentences and better explanations

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
.. todo::

   Implement filters for the device table view.
   Improve how missing memory values are fetched.
   Implement device panels and specialized device functionality available to
   scripts.
   Refactor DeviceDescription to DeviceProfile.
   Implement polling

* device table view
* device profiles
* specialized device panels
* unsupported devices

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

Scripting
---------
Scripting support both in the GUI and from the command line is available using
Python scripts.

.. include:: scripting.rst
.. todo::

   Implement and unit test the scripting functionality. 
   Device specific functions/methods should be available and usable in scripts
   as well as in the GUI.


.. .. automodule:: mesycontrol.app_model
   :members:
   :undoc-members:
   :special-members:

Network protocol
----------------
Message Format
^^^^^^^^^^^^^^
The message format is: <**size**> <**type_code**> <**type_dependent_data**>

**size** is a 2 byte *unsigned integer* specifying the size of the following
message - including the **type_code** byte - in bytes. This field is used to
validate the received data as the correct message size is known by looking at
the **type_code** field.

Multibyte numeric data is encoded in network byte order.

Communication largely follows the request-response model: The mesycontrol
client sends a single request to the server, then waits for a response to
arrive. Additionally the server sends out notification messages to propagate
state changes to all connected clients.

Data Types
^^^^^^^^^^

+------------+----------+---------------------+---------------------------------------------------------------+
| **Name**   | **Size** | **Range**           | **Description**                                               |
+============+==========+=====================+===============================================================+
| msg_type   | 1 Byte   | enum                | Message type code. See below for valid values.                |
+------------+----------+---------------------+---------------------------------------------------------------+
| bus        | 1 Byte   | [0..1]              | Mesytec RC bus number.                                        |
+------------+----------+---------------------+---------------------------------------------------------------+
| dev        | 1 Byte   | [0..15]             | Device bus address.                                           |
+------------+----------+---------------------+---------------------------------------------------------------+
| par        | 1 Byte   | [0..255]            | Parameter memory address.                                     |
+------------+----------+---------------------+---------------------------------------------------------------+
| val        | 4 Bytes  | [-(2^31-1)..2^31-1] | Parameter value.                                              |
+------------+----------+---------------------+---------------------------------------------------------------+
| idc        | 1 Byte   | [0..255]            | Device ID code. 0 means no device is present.                 |
+------------+----------+---------------------+---------------------------------------------------------------+
| error_code | 1 Byte   | enum                | Error codes. See below for a list of codes and their meaning. |
+------------+----------+---------------------+---------------------------------------------------------------+
| bool_value | 1 Byte   | [0..1]              | Boolean value.                                                |
+------------+----------+---------------------+---------------------------------------------------------------+

Request Messages
^^^^^^^^^^^^^^^^

.. include:: protocol_requests.rst

Response Messages
^^^^^^^^^^^^^^^^^

.. include:: protocol_responses.rst

Notification Messages
^^^^^^^^^^^^^^^^^^^^^

.. include:: protocol_notifications.rst

Error Codes
^^^^^^^^^^^
.. include:: protocol_error_codes.rst

TODOS
=====
.. todolist::

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

