#include "serverworker.h"
#include <QMetaObject>
#include <QMutexLocker>
#include <QDateTime>
#include <QCoreApplication>
#include <QStringList>
#include <boost/thread.hpp>
#include <boost/date_time.hpp>

ServerWorker::ServerWorker(QxtRPCPeer *rpc, int worker_id, QMutex *rpc_lock)
   : m_rpc(rpc)
   , m_worker_id(worker_id)
   , m_rpc_lock(rpc_lock)
{
   connect(this, SIGNAL(destroyed()), rpc, SLOT(detachSender()));
   connect(&m_timer, SIGNAL(timeout()), this, SLOT(handle_timer_timeout()));
   m_timer.setInterval(10);
   m_timer.start();
}

void ServerWorker::handle_timer_timeout()
{
   QStringList data;
   
   for (int i=0; i<10; ++i)
      data.push_back(QString::number(qrand()));

   //QMutexLocker locker(m_rpc_lock);
   //m_rpc->call("high_freq_method", m_worker_id, QVariant::fromValue(data));
   QMetaObject::invokeMethod(m_rpc, "call", Qt::QueuedConnection,
         Q_ARG(QString, "high_freq_method"),
         Q_ARG(QVariant, m_worker_id),
         Q_ARG(QVariant, QVariant::fromValue(data)));
}
