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
* Tabular view of the device memory.
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

Using mesycontrol
-----------------

Architecture Overview
---------------------

Graphical User Interface
------------------------

Scripting
---------

.. .. automodule:: mesycontrol.app_model
   :members:
   :undoc-members:
   :special-members:


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

