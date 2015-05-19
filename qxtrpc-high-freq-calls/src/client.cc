#include "client.h"
#include <QTimer>
#include <QDateTime>

Client::Client()
{
   rpc.connect("localhost", 54213);
   rpc.attachSlot("high_freq_method", this, SLOT(high_freq_method(int, const QStringList &)));
}

void Client::high_freq_method(int worker_id, const QStringList &data)
{
   qDebug() << QDateTime::currentDateTime()
      << "high_freq_method: worker_id =" << worker_id << ", data =" << data.join(", ");
}
