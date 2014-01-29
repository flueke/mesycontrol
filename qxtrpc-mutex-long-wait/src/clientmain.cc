#include "client.h"
#include <QCoreApplication>

int main(int argc, char *argv[])
{
   QCoreApplication app(argc, argv);

   Client client;

   return app.exec();
}

