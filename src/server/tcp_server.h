#ifndef UUID_56885668_cb99_4f4a_8074_cb1aa435e750
#define UUID_56885668_cb99_4f4a_8074_cb1aa435e750

#include "config.h"
#include <boost/asio.hpp>
#include <boost/noncopyable.hpp>
#include "tcp_connection_manager.h"
#include <mesycontrol/protocol.h>

namespace mesycontrol
{

class TCPServer: private boost::noncopyable
{
  public:
    explicit TCPServer(boost::asio::io_service &io_service,
        boost::asio::ip::tcp::endpoint endpoint, RequestHandler req_handler);
    ~TCPServer();

    void stop();

  private:
    void start_accept();
    void handle_accept(const boost::system::error_code &ec);


    boost::asio::io_service &io_service_;
    boost::asio::ip::tcp::acceptor acceptor_;
    TCPConnectionManager connection_manager_;
    TCPConnectionPtr new_connection_;
    RequestHandler request_handler_;
};

} // namespace mesycontrol

#endif
