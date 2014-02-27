#ifndef UUID_d95784cc_3420_49a5_b6a1_4b07db64a8fe
#define UUID_d95784cc_3420_49a5_b6a1_4b07db64a8fe

#include <QObject>
#include <boost/exception/all.hpp>
#include <boost/thread.hpp>
#include "tcp_client.h"

namespace mesycontrol
{

/* Qt integration of the boost::asio based TCPClient class.  QtTCPClient runs
 * TCPClient in a dedicated IO thread so it does not block the Qt event loop.
 * Signals will be emitted from within this IO thread so Qt::QueuedConnections
 * should be used for signal connections.
 */
class QtTCPClient: public QObject
{
  Q_OBJECT
  public:
    QtTCPClient(QObject *parent = 0);
    ~QtTCPClient();

    bool is_connected() const;

  public slots:
    /** Starts the internal IO service. */
    void start();

    /** Stops the internal IO service. */
    void stop();

    void connect(const QString &hostname, unsigned short port);
    void disconnect();
    void queue_request(const mesycontrol::MessagePtr &msg);

  signals:
    void connecting();
    void connected();
    void disconnected();
    void client_error(const boost::system::error_code &ec);
    void response_received(const mesycontrol::MessagePtr &, const mesycontrol::MessagePtr &);

  private:
    void io_thread_work(boost::exception_ptr &error);
    void response_handler(const MessagePtr &request, const MessagePtr &response);
    void boost_slt_connecting() { emit connecting(); }
    void boost_slt_connected()  { emit connected(); }
    void boost_slt_disconnected() { emit disconnected(); }
    void boost_slt_error(const boost::system::error_code &ec)
    { emit client_error(ec); }
    
    boost::asio::io_service m_io_service;
    boost::scoped_ptr<boost::asio::io_service::work> m_io_work;
    boost::scoped_ptr<boost::thread> m_io_thread;
    boost::exception_ptr m_io_error;
    boost::shared_ptr<TCPClient> m_client;
};

} // namespace mesycontrol

#endif
