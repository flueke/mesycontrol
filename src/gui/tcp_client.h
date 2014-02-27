#ifndef UUID_58b6e1c6_a658_437d_9cfa_88bef33193d1
#define UUID_58b6e1c6_a658_437d_9cfa_88bef33193d1

#include "config.h"
#include <boost/asio.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/noncopyable.hpp>
#include <boost/signals2.hpp>
#include <boost/system/error_code.hpp>
#include <string>
#include <queue>
#include <mesycontrol/protocol.h>

namespace mesycontrol
{

class TCPClient:
  public boost::enable_shared_from_this<TCPClient>,
  private boost::noncopyable
{
  public:
    typedef boost::signals2::signal<void ()> void_signal;
    typedef boost::signals2::signal<void (const boost::system::error_code &)> error_code_signal;
    typedef boost::function<void (const MessagePtr &, const MessagePtr &)> ResponseHandler;

    explicit TCPClient(boost::asio::io_service &io_service);

    void connect(const std::string &hostname, const std::string &service);
    void connect(const std::string &hostname, unsigned short port);
    void disconnect();
    bool is_connected() const;

    void queue_request(const MessagePtr &msg, ResponseHandler response_handler);

    boost::signals2::connection connect_sig_connecting(const void_signal::slot_type &slot);
    boost::signals2::connection connect_sig_connected(const void_signal::slot_type &slot);
    boost::signals2::connection connect_sig_disconnected(const void_signal::slot_type &slot);
    boost::signals2::connection connect_sig_error(const error_code_signal::slot_type &slot);

  private:
    void handle_resolve(const boost::system::error_code &ec, boost::asio::ip::tcp::resolver::iterator it);
    void handle_connect(const boost::system::error_code &ec, boost::asio::ip::tcp::resolver::iterator it);

    void start_write_message();
    void handle_write_message(const boost::system::error_code &ec, size_t n_bytes);

    void start_read_message_size();
    void handle_read_message_size(const boost::system::error_code &ec, size_t n_bytes);

    void start_read_message();
    void handle_read_message(const boost::system::error_code &ec, size_t n_bytes);

    void start_deadline(const boost::posix_time::time_duration &duration);
    void cancel_deadline();
    void handle_deadline(const boost::system::error_code &ec);

    boost::asio::io_service &m_io_service;
    boost::asio::ip::tcp::resolver m_resolver;
    boost::asio::ip::tcp::socket m_socket;
    boost::asio::deadline_timer m_deadline;

    std::string m_hostname;
    std::string m_port;

    typedef std::deque<std::pair<MessagePtr, ResponseHandler> > RequestQueue;
    RequestQueue m_request_queue;

    uint16_t m_request_size;
    std::vector<unsigned char> m_request_buffer;

    uint16_t m_response_size;
    std::vector<unsigned char> m_response_buffer;
    
    void_signal sig_connecting;
    void_signal sig_connected;
    void_signal sig_disconnected;
    error_code_signal sig_error;
};

} // namespace mesycontrol

#endif
