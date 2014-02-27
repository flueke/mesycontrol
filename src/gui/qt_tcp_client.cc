#include <QDebug>
#include "qt_tcp_client.h"

namespace mesycontrol
{

QtTCPClient::QtTCPClient(QObject *parent):
  QObject(parent),
  m_client(new TCPClient(m_io_service))
{
  m_client->connect_sig_connecting(boost::bind(&QtTCPClient::boost_slt_connecting, this));
  m_client->connect_sig_connected(boost::bind(&QtTCPClient::boost_slt_connected, this));
  m_client->connect_sig_disconnected(boost::bind(&QtTCPClient::boost_slt_disconnected, this));
  m_client->connect_sig_error(boost::bind(&QtTCPClient::boost_slt_error, this, _1));
}

QtTCPClient::~QtTCPClient()
{
  stop();
}

bool QtTCPClient::is_connected() const
{
  return m_client->is_connected();
}

void QtTCPClient::start()
{
  if (m_io_thread)
    return;

  m_io_work.reset(new boost::asio::io_service::work(m_io_service));
  m_io_thread.reset(new boost::thread(boost::bind(&QtTCPClient::io_thread_work, this, m_io_error)));
}

void QtTCPClient::stop()
{
  if (!m_io_thread)
    return;

  disconnect();
  m_io_work.reset();
  m_io_service.stop();
  m_io_thread->join();
  m_io_thread.reset();
}

void QtTCPClient::connect(const QString &hostname, unsigned short port)
{
  start();

  void (TCPClient::*connector)(const std::string &, unsigned short) = &TCPClient::connect;
  m_io_service.post(boost::bind(connector, m_client, hostname.toStdString(), port));
}

void QtTCPClient::disconnect()
{
  m_client->disconnect();
}

void QtTCPClient::queue_request(const mesycontrol::MessagePtr &msg)
{
  qDebug() << __PRETTY_FUNCTION__;
  m_client->queue_request(msg, boost::bind(&QtTCPClient::response_handler, this, _1, _2));
}

void QtTCPClient::response_handler(const MessagePtr &req, const MessagePtr &resp)
{
  qDebug() << __PRETTY_FUNCTION__;
  emit response_received(req, resp);
}

void QtTCPClient::io_thread_work(boost::exception_ptr &error)
{
  try {
    m_io_service.run();
    error = boost::exception_ptr();
  } catch (...) {
    error = boost::current_exception();
  }
}

} // namespace mesycontrol
