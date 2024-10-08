# 1.2.0

  - Improved scripting support and more example scripts.

  - Rewrite internal packaging recipe to use pyproject.toml instead of the obsolete setup.py.

  - Fixes for dangling references to c++ objects. Issues with QProcess still
    remain but these only manifest on system shutdown.

  - Fully dockerized use is now possible. See Dockerfile.ubuntu-22.04 for details.

# 1.1.7

  - Better log handling: avoid excessive log spam on error.
  - MPRB-16-DR: auto poll sum_current, temperature and error_code registers.
  - MSCF-16: fix runtime error from auto_pz logic
  - Fix stack overflow due to recursion in the TCP client code.
  - Add Dockerfile to test building under debian stable.
  - Internal python2 to python3 related fixes.
  - Internal packaging fixes.

# 1.1.6

  - Revive scripting support which did not work since porting to python3.

# 1.1.5

  - MPD-4: make **qwin** values read-only. Workaround for a bug in the MPD-4
    where qwin values cannot be properly set via the RC-Bus.

# 1.1.4

  - Fix the windows start menu icon
  - Fix version display in 'Help -> About'
  - Releases are now built against Qt-5.15 and more recent python versions

# 1.1.3

  - Fix protobuf message truncation issue.
  - MPRB-16(-DR): set correct current offset in device profile
  - MHV-4: fix LCD update code
  - Disable console for windows builds.

# 1.1.2

  - MSCF-16: properly disable upper threshold inputs if WindowDiscriminator is
    not supported
  - MSCF-16: show FPGA firmware version in hex so that the value is the same as
    in the firmware update filenames

# 1.1.1

  - Fix broken Device Table View
  - Add option to show register values in hex in the Device Table View
  - Fix a QProcess related crash on exit
  - CMake build and packaging fixes

# 1.1.0

  Major update: ported from Python2/PyQt4 to Python3/PySide2/Qt5 to stay
  compatible with newer linux distributions and make a future port to Qt6
  easier.

  While porting several existing bugs and issues have been fixed and the GUI
  was improved with new icons, button labels and some layout changes.

  Note: as these where major changes some new issues may have been introduced
  due to subtle differences between PyQt4 and PySide2.

# 1.0.6.2

  - Linux only: the package now contains the Qt4 libraries to make the client
    work on newer linux distributions.

# 1.0.6.1

  - Add limited support for the older MHV-4-V20-400V model with idc code 17.

# 1.0.5

  - Support the Window Discriminator found on some newer MSCF-16 versions. In
    the MSCF GUI a column called "Upper Thresholds" has been added
    and is enabled if WinDis support has been detected.
