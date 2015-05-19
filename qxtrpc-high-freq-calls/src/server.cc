#include "server.h"
#include <QMutexLocker>
#include <QDateTime>
#include <QCoreApplication>
#include <QStringList>
#include <boost/thread.hpp>
#include <boost/date_time.hpp>

Server::Server()
   : m_rpc(new QxtRPCPeer(this))
{
   //connect(this, SIGNAL(destroyed()), &m_rpc, SLOT(detachSender()));
   m_rpc->listen(QHostAddress::LocalHost, 54213);

   for (int i=0; i<20; ++i) {
      QThread *thread = new QThread;
      QSharedPointer<ServerWorker> worker(QSharedPointer<ServerWorker>(new ServerWorker(m_rpc, i, &m_rpc_lock)));
      worker->moveToThread(thread);
      QTimer::singleShot(0, thread, SLOT(start()));
      m_workers.push_back(worker);
   }
}

Server::~Server()
{
   for (int i=0; i<m_workers.size(); ++i) {
      QSharedPointer<ServerWorker> worker(m_workers[i]);
      worker->thread()->quit();
      worker->thread()->wait();
      worker->thread()->deleteLater();
   }
}
