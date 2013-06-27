#include "main_object.h"
#include <QApplication>
int main(int argc, char *argv[])
{
   QApplication app(argc, argv);

   MainObject main_object;
   return app.exec();
}
