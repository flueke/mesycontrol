#include <QApplication>
#include <QMetaType>
#include <mesycontrol/protocol.h>
#include "mainwin.h"

using namespace mesycontrol;

int main(int argc, char *argv[])
{
  QApplication app(argc, argv);
  qRegisterMetaType<mesycontrol::MessagePtr>("mesycontrol::MessagePtr");
  qRegisterMetaType<boost::system::error_code>("boost::system::error_code");
  Mainwin mainwin;
  mainwin.show();
  return app.exec();
}
