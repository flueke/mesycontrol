#ifndef UUID_8562410b_7a36_4752_a390_2af066330867
#define UUID_8562410b_7a36_4752_a390_2af066330867

#include <QObject>
#include <QxtRPCPeer>
#include <QMutex>
#include <QTimer>

class ServerWorker: public QObject
{
   Q_OBJECT
   public:
      ServerWorker(QxtRPCPeer *rpc, int worker_id, QMutex *rpc_lock);

   private slots:
      void handle_timer_timeout();

   private:
      QxtRPCPeer *m_rpc;
      int m_worker_id;
      QMutex *m_rpc_lock;
      QTimer m_timer;
};

#endif
