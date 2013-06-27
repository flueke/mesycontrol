#include <QApplication>
#include <QDoubleSpinBox>
int main(int argc, char *argv[])
{
   QApplication app(argc, argv);

   QDoubleSpinBox spinbox;
   spinbox.setLocale(QLocale::c());
   spinbox.show();

   return app.exec();
}
