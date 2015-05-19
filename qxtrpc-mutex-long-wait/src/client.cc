#include "client.h"
#include <QTimer>
#include <QDateTime>

Client::Client()
   : invocation_count(0)
   , pending_replies(0)
{
   rpc.connect("localhost", 54213);
   rpc.attachSlot("the_reply_method", this, SLOT(the_reply_method(int)));

   for (int i=0; i<10; ++i)
      QTimer::singleShot(250 * (i+1), this, SLOT(invoke_remote()));
}

void Client::invoke_remote()
{
   ++invocation_count;
   ++pending_replies;
   qDebug() << QDateTime::currentDateTime() << "arg =" << invocation_count << "calling the_reply_method";
   rpc.call("the_rpc_method", invocation_count);
}

void Client::the_reply_method(int arg)
{
   --pending_replies;
   qDebug() << QDateTime::currentDateTime() << "arg =" << arg << "pending replies = " << pending_replies;
}
