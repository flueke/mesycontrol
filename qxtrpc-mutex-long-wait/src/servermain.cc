#include "server.h"
#include <QCoreApplication>
#include <QThread>
#include <QTimer>

int main(int argc, char *argv[])
{
   QCoreApplication app(argc, argv);

   QxtRPCPeer rpc;

   Server server(rpc);
   return app.exec();
}
