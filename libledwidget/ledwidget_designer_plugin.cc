#include "ledwidget_designer_plugin.h"
#include <QtPlugin>
#include "ledwidget.h"

LEDWidgetDesignerPlugin::LEDWidgetDesignerPlugin(QObject *parent)
   : QObject(parent)
   , initialized(false)
{}

bool     LEDWidgetDesignerPlugin::isContainer() const { return false; }
bool     LEDWidgetDesignerPlugin::isInitialized() const { return initialized; }
QIcon    LEDWidgetDesignerPlugin::icon() const { return QIcon(); }
QString  LEDWidgetDesignerPlugin::group() const { return "Custom Widgets"; }
QString  LEDWidgetDesignerPlugin::includeFile() const { return "ledwidget.h"; }
QString  LEDWidgetDesignerPlugin::name() const { return "LEDWidget"; }
QString  LEDWidgetDesignerPlugin::toolTip() const { return ""; }
QString  LEDWidgetDesignerPlugin::whatsThis() const { return ""; }
QWidget *LEDWidgetDesignerPlugin::createWidget(QWidget *parent) { return new LEDWidget(parent); }

QString  LEDWidgetDesignerPlugin::domXml() const
{
        return "<ui language=\"c++\">\n"
            " <widget class=\"LEDWidget\" name=\"ledWidget\">\n"
            "  <property name=\"geometry\">\n"
            "   <rect>\n"
            "    <x>0</x>\n"
            "    <y>0</y>\n"
            "    <width>16</width>\n"
            "    <height>16</height>\n"
            "   </rect>\n"
            "  </property>\n"
            " </widget>\n"
            "</ui>\n";
}

void     LEDWidgetDesignerPlugin::initialize(QDesignerFormEditorInterface *)
{
   if (initialized) return;
   initialized = true;
}

Q_EXPORT_PLUGIN2(ledwidgetdesignerplugin, LEDWidgetDesignerPlugin)
