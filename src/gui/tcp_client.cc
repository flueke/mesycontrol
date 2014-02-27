#include "tcp_client.h"
#include <iostream>
#include <boost/bind.hpp>
#include <boost/lexical_cast.hpp>

namespace asio = boost::asio;
using asio::ip::tcp;

namespace mesycontrol
{

TCPClient::TCPClient(asio::io_service &io_service)
  : m_io_service(io_service)
  , m_resolver(io_service)
  , m_socket(io_service)
  , m_deadline(io_service)
{}

void TCPClient::connect(const std::string &hostname, const std::string &service_or_port)
{
  disconnect();
  sig_connecting();

  tcp::resolver::query query(tcp::v4(), hostname, service_or_port);
  m_resolver.async_resolve(query,
      boost::bind(&TCPClient::handle_resolve, shared_from_this(), _1, _2));
}

void TCPClient::connect(const std::string &hostname, unsigned short port)
{
  connect(hostname, boost::lexical_cast<std::string>(port));
}

void TCPClient::disconnect()
{
  bool was_connected(is_connected());

  boost::system::error_code ignored_ec;
  m_socket.close(ignored_ec);

  if (was_connected)
    sig_disconnected();
}

bool TCPClient::is_connected() const
{
  return m_socket.is_open();
}

void TCPClient::handle_resolve(const boost::system::error_code& ec,
      tcp::resolver::iterator endpoint_iterator)
{
  if (!ec) {
    /* Synchronous connect due to https://svn.boost.org/trac/boost/ticket/8795 */
    boost::system::error_code ec;
    tcp::resolver::iterator endpoint = asio::connect(m_socket, endpoint_iterator, ec);
    handle_connect(ec, endpoint);
  } else {
    std::cout << "Resolve error: " << ec.message() << std::endl;
    sig_error(ec);
  }
}

void TCPClient::handle_connect(const boost::system::error_code &ec, tcp::resolver::iterator endpoint)
{
  if (!ec && m_socket.is_open() && endpoint != tcp::resolver::iterator()) {
    std::cout << "Connected!" << std::endl;
    m_socket.set_option(asio::ip::tcp::no_delay(true));
    sig_connected();
    start_write_message();
  } else {
    /* Even if the connect failed socket.is_open() returns true and the client
     * would think it is connected. To avoid this we close the socket here. */
    boost::system::error_code ignored_ec;
    m_socket.close(ignored_ec);
    std::cout << "Could not connect:" << ec.message() << std::endl;
    sig_error(ec);
  }
}

void TCPClient::queue_request(const MessagePtr &request, ResponseHandler response_handler)
{
  bool was_empty(m_request_queue.empty());
  m_request_queue.push_back(std::make_pair(request, response_handler));
  if (was_empty) {
    start_write_message();
  }
}

boost::signals2::connection TCPClient::connect_sig_connecting(const void_signal::slot_type &slot)
{
  return sig_connecting.connect(slot);
}

boost::signals2::connection TCPClient::connect_sig_connected(const void_signal::slot_type &slot)
{
  return sig_connected.connect(slot);
}

boost::signals2::connection TCPClient::connect_sig_disconnected(const void_signal::slot_type &slot)
{
  return sig_disconnected.connect(slot);
}

boost::signals2::connection TCPClient::connect_sig_error(const error_code_signal::slot_type &slot)
{
  return sig_error.connect(slot);
}

void TCPClient::start_write_message()
{
  if (m_request_queue.empty()) {
    std::cout << __PRETTY_FUNCTION__ << "empty queue" << std::endl;
    return;
  }

  m_request_buffer = m_request_queue.front().first->serialize();
  m_request_size   = htons(m_request_buffer.size());

  boost::array<asio::const_buffer, 2> buffers =
  {
    asio::buffer(&m_request_size, 2),
    asio::buffer(m_request_buffer)
  };

  asio::async_write(m_socket, buffers,
      boost::bind(&TCPClient::handle_write_message, shared_from_this(), _1, _2));
}

void TCPClient::handle_write_message(const boost::system::error_code &ec, size_t n_bytes)
{
  if (!ec) {
    start_read_message_size();
  } else {
    m_request_queue.front().second(m_request_queue.front().first, Message::make_error_response(error_type::mrc_comm_error));
    m_request_queue.pop_front();
    std::cout << "Error: " << ec.message() << std::endl;
    sig_error(ec);
    disconnect();
  }
}

void TCPClient::start_read_message_size()
{
  asio::async_read(m_socket, asio::buffer(&m_response_size, 2),
      boost::bind(&TCPClient::handle_read_message_size, shared_from_this(), _1, _2));
}

void TCPClient::handle_read_message_size(const boost::system::error_code &ec, size_t n_bytes)
{
  if (!ec) {
    m_response_size = ntohs(m_response_size);
    m_response_buffer.clear();
    std::cout << "Expected response size = " << m_response_size << std::endl;
    m_response_buffer.resize(m_response_size);
    start_read_message();
  } else {
    m_request_queue.front().second(m_request_queue.front().first, Message::make_error_response(error_type::mrc_comm_error));
    m_request_queue.pop_front();
    std::cout << "Error: " << ec.message() << std::endl;
    sig_error(ec);
    disconnect();
  }
}

void TCPClient::start_read_message()
{
  asio::async_read(m_socket, asio::buffer(m_response_buffer),
      boost::bind(&TCPClient::handle_read_message, shared_from_this(), _1, _2));
}

void TCPClient::handle_read_message(const boost::system::error_code &ec, size_t n_bytes)
{
  if (!ec) {
    MessagePtr msg(Message::deserialize(m_response_buffer));
    m_request_queue.front().second(m_request_queue.front().first, msg);
    m_request_queue.pop_front();
    start_write_message();
  } else {
    m_request_queue.front().second(m_request_queue.front().first, Message::make_error_response(error_type::mrc_comm_error));
    m_request_queue.pop_front();
    std::cout << "Error: " << ec.message() << std::endl;
    sig_error(ec);
    disconnect();
  }
}

} // namespace mesycontrol
