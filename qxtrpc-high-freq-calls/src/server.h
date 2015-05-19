#ifndef UUID_1c2efa63_6959_4478_b6a6_4a9a848952e3
#define UUID_1c2efa63_6959_4478_b6a6_4a9a848952e3

#include <QObject>
#include <QxtRPCPeer>
#include <QMutex>
#include <QTimer>
#include <QThread>
#include <QSharedPointer>
#include <QList>
#include "serverworker.h"

class Server: public QObject
{
   Q_OBJECT
   public:
      Server();
      ~Server();

   private:
      QxtRPCPeer *m_rpc;
      QList<QSharedPointer<ServerWorker> > m_workers;
      QMutex m_rpc_lock;
};

#endif
