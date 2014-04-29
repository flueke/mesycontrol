#ifndef UUID_56885668_cb99_4f4a_8074_cb1aa435e750
#define UUID_56885668_cb99_4f4a_8074_cb1aa435e750

#include "config.h"
#include <boost/asio.hpp>
#include <boost/noncopyable.hpp>
#include "tcp_connection_manager.h"
#include "protocol.h"
#include "logging.h"

namespace mesycontrol
{

class TCPServer: private boost::noncopyable
{
  public:
    explicit TCPServer(boost::asio::io_service &io_service,
        boost::asio::ip::tcp::endpoint endpoint,
        TCPConnectionManager &connection_manager);
    ~TCPServer();

    void stop();

  private:
    void start_accept();
    void handle_accept(const boost::system::error_code &ec);


    boost::asio::io_service &m_io_service;
    boost::asio::ip::tcp::acceptor m_acceptor;
    TCPConnectionManager &m_connection_manager;
    TCPConnectionPtr m_new_connection;
    log::Logger m_log;
};

} // namespace mesycontrol

#endif
