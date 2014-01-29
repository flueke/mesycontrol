#include "server.h"
#include <QMutexLocker>
#include <QDateTime>
#include <QTimer>
#include <QCoreApplication>
#include <boost/thread.hpp>
#include <boost/date_time.hpp>

Server::Server(QxtRPCPeer &rpc)
   : rpc(rpc)
{
   connect(this, SIGNAL(destroyed()), &rpc, SLOT(detachSender()));

   rpc.attachSlot("the_rpc_method", this, SLOT(the_rpc_method(quint64, int)));

   rpc.listen(QHostAddress::LocalHost, 54213);
}

void Server::the_rpc_method(quint64 cid, int arg)
{
   qDebug() << QDateTime::currentDateTime() << "arg =" << arg << "aquiring lock";
   QMutexLocker locker(&m_lock);
   qDebug() << QDateTime::currentDateTime() << "arg =" << arg << "lock aquired. starting work";
   boost::this_thread::sleep(boost::posix_time::seconds(5));
   qDebug() << QDateTime::currentDateTime() << "arg =" << arg << "work done";
   rpc.call(cid, "the_reply_method", arg);
   qDebug() << QDateTime::currentDateTime() << "arg =" << arg << "leaving method";
}
