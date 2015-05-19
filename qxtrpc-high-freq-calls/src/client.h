#ifndef UUID_bd5c14ce_1ce7_48e3_a442_c4a67fba2976
#define UUID_bd5c14ce_1ce7_48e3_a442_c4a67fba2976

#include <QObject>
#include <QxtRPCPeer>
#include <QStringList>

class Client: public QObject
{
   Q_OBJECT
   public:
      Client();

   private slots:
      void high_freq_method(int worker_id, const QStringList &data);

   private:
      QxtRPCPeer rpc;
};

#endif
