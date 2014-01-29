#ifndef UUID_bd5c14ce_1ce7_48e3_a442_c4a67fba2976
#define UUID_bd5c14ce_1ce7_48e3_a442_c4a67fba2976

#include <QObject>
#include <QxtRPCPeer>

class Client: public QObject
{
   Q_OBJECT
   public:
      Client();

   private slots:
      void invoke_remote();
      void the_reply_method(int arg);

   private:
      QxtRPCPeer rpc;
      int invocation_count;
      int pending_replies;
};

#endif
