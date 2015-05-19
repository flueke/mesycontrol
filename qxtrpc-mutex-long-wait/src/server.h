#ifndef UUID_1c2efa63_6959_4478_b6a6_4a9a848952e3
#define UUID_1c2efa63_6959_4478_b6a6_4a9a848952e3

#include <QObject>
#include <QxtRPCPeer>
#include <QMutex>

class Server: public QObject
{
   Q_OBJECT
   public:
      Server(QxtRPCPeer &rpc);

   public slots:
      void the_rpc_method(quint64 cid, int arg);

   private:
      QxtRPCPeer &rpc;
      QMutex m_lock;
};

#endif
