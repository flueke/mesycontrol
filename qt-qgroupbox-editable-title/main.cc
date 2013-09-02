#include "qgroupbox_editable_title.h"
#include <QApplication>

int main(int argc, char *argv[])
{
   QApplication app(argc, argv);

#if 1
   GroupBox groupbox("Example Title");
   groupbox.setCheckable(true);
   groupbox.setFixedSize(150, 200);
   groupbox.show();
#endif

   GroupBox groupbox2("Example Title 2");
   groupbox2.setFixedSize(150, 200);
   groupbox2.show();

   return app.exec();
}
