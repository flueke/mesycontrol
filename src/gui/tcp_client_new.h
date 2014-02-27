#ifndef UUID_58b6e1c6_a658_437d_9cfa_88bef33193d1
#define UUID_58b6e1c6_a658_437d_9cfa_88bef33193d1

#include "config.h"
#include <boost/asio.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/signals2.hpp>
#include <boost/system/error_code.hpp>
#include <boost/utility.hpp>
#include <string>
#include <mesycontrol/protocol.h>

namespace mesycontrol
{

class TCPClient:
  public boost::enable_shared_from_this<TCPClient>,
  private boost::noncopyable
{
  public:
    explicit TCPClient(boost::asio::io_service &io_service);

    void connect(const std::string &hostname, const std::string &service);
    void connect(const std::string &hostname, unsigned short port);
    void disconnect();
    bool is_connected() const;

    void send_message(const MessagePtr &msg, boost::function<void (const MessagePtr &, const MessagePtr &)> response_handler);

    typedef boost::signals2::signal<void ()> void_signal;
    typedef boost::signals2::signal<void (const boost::system::error_code &)> ec_signal;

  private:
    void_signal sig_connecting;
    void_signal sig_connected;
    void_signal sig_disconnected;
    ec_signal   sig_error;

    std::string m_hostname;
    std::string m_port;
    boost::asio::io_service &m_io_service;
    boost::asio::ip::tcp::resolver m_resolver;
    boost::asio::ip::tcp::socket m_socket;
};

#endif
