#ifndef UUID_c0a64b2d_e83b_48e5_a81a_7867fe70fb0c
#define UUID_c0a64b2d_e83b_48e5_a81a_7867fe70fb0c

#include "config.h"
#include <boost/asio.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/noncopyable.hpp>
#include <boost/shared_ptr.hpp>
#include <mesycontrol/protocol.h>
#include "handler_types.h"

namespace mesycontrol
{

class TCPConnectionManager;

class TCPConnection
  : public boost::enable_shared_from_this<TCPConnection>
  , private boost::noncopyable
{
  public:
    explicit TCPConnection(boost::asio::io_service &io_service,
        TCPConnectionManager &manager,
        RequestHandler request_handler);

    ~TCPConnection();

    void start();
    void stop();

    boost::asio::ip::tcp::socket &socket();

  private:
    void start_read_request_size();
    void handle_read_request_size(const boost::system::error_code &ec, std::size_t n_bytes);

    void start_read_request();
    void handle_read_request(const boost::system::error_code &ec, std::size_t n_bytes);

    void start_write_response();
    void handle_write_response(const boost::system::error_code &ec, std::size_t n_bytes);

    void response_ready_callback(const MessagePtr &request, const MessagePtr &reply);

    boost::asio::ip::tcp::socket socket_;
    TCPConnectionManager &connection_manager_;
    RequestHandler request_handler_;

    uint16_t request_size_;
    std::vector<unsigned char> request_buf_;

    uint16_t response_size_;
    std::vector<unsigned char> response_buf_;
};

typedef boost::shared_ptr<TCPConnection> TCPConnectionPtr;

} // namespace mesycontrol

#endif
