#ifndef UUID_c0a64b2d_e83b_48e5_a81a_7867fe70fb0c
#define UUID_c0a64b2d_e83b_48e5_a81a_7867fe70fb0c

#include "config.h"
#include <boost/asio.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/noncopyable.hpp>
#include <boost/shared_ptr.hpp>
#include <queue>
#include "protocol.h"
#include "logging.h"

namespace mesycontrol
{

class TCPConnectionManager;

class TCPConnection
  : public boost::enable_shared_from_this<TCPConnection>
  , private boost::noncopyable
{
  public:
    explicit TCPConnection(boost::asio::io_service &io_service, TCPConnectionManager &manager);
    ~TCPConnection();

    void start();
    void stop();

    boost::asio::ip::tcp::socket &socket();
    void send_message(const MessagePtr &msg);
    std::string connection_string() const;

  private:
    void start_read_message_size();
    void handle_read_message_size(const boost::system::error_code &ec, std::size_t n_bytes);

    void start_read_message();
    void handle_read_message(const boost::system::error_code &ec, std::size_t n_bytes);

    void start_write_message();
    void handle_write_message(const boost::system::error_code &ec, std::size_t n_bytes);

    boost::asio::ip::tcp::socket m_socket;
    TCPConnectionManager &m_connection_manager;

    uint16_t m_read_size;
    std::vector<unsigned char> m_read_buf;

    uint16_t m_write_size;
    std::vector<unsigned char> m_write_buf;

    std::deque<MessagePtr> m_write_queue;
    bool m_write_in_progress;

    std::string m_connection_string;

    log::Logger m_log;
};

typedef boost::shared_ptr<TCPConnection> TCPConnectionPtr;

} // namespace mesycontrol

#endif
