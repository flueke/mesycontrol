# 1.1.1

  - Fix broken Device Table View

  - Add option to show register values in hex in the Device Table View

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

