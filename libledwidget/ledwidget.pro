CONFIG     += designer plugin
TEMPLATE    = lib
TARGET      = $$qtLibraryTarget($$TARGET)
DEPENDPATH += .
INCLUDEPATH += .

# Input
HEADERS += ledwidget.h ledwidget_designer_plugin.h
SOURCES += ledwidget.cc ledwidget_designer_plugin.cc
