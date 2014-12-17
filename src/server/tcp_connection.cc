#ifndef __MINGW32__
#include <arpa/inet.h>
#endif
#include <boost/bind.hpp>
#include <boost/format.hpp>
#include <boost/log/trivial.hpp>
#include "tcp_connection.h"
#include "tcp_connection_manager.h"

namespace asio = boost::asio;

namespace mesycontrol
{

TCPConnection::TCPConnection(boost::asio::io_service &io_service, TCPConnectionManager &manager)
  : m_socket(io_service)
  , m_connection_manager(manager)
  , m_write_in_progress(false)
  , m_log(log::keywords::channel="TCPConnection")
  , m_stopping(false)
  , m_read_size(0)
  , m_write_size(0)
{
}

TCPConnection::~TCPConnection()
{
  stop(false);
}

void TCPConnection::start()
{
  static boost::format fmt("%1%:%2%");
  m_connection_string = boost::str(fmt
      % m_socket.remote_endpoint().address().to_string()
      % m_socket.remote_endpoint().port());

  BOOST_LOG_SEV(m_log, log::lvl::info) << "New connection from " << connection_string();

  m_socket.set_option(asio::ip::tcp::no_delay(true));
  start_read_message_size();
}

void TCPConnection::stop(bool graceful)
{
  if (m_socket.is_open() && graceful && (!m_write_queue.empty() || m_write_in_progress)) {
    m_stopping = true;
  } else if (m_socket.is_open()) {
    BOOST_LOG_SEV(m_log, log::lvl::info) << "Closing connection from " << connection_string();
    m_socket.close();
  }
}

boost::asio::ip::tcp::socket &TCPConnection::socket()
{
  return m_socket;
}

void TCPConnection::send_message(const MessagePtr &msg)
{
  if (m_stopping) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << connection_string()
      << ": connection is stopping, discarding outgoing message!";
    return;
  }

  BOOST_LOG_SEV(m_log, log::lvl::trace) << connection_string()
    << ": adding message of type " << msg->get_info_string() << " to the outgoing queue";
  m_write_queue.push_back(msg);
  start_write_message();
}

void TCPConnection::start_read_message_size()
{
  if (m_stopping)
    return;

  BOOST_LOG_SEV(m_log, log::lvl::trace) << connection_string() << ": reading message size";

  asio::async_read(m_socket, asio::buffer(&m_read_size, 2),
      boost::bind(&TCPConnection::handle_read_message_size, shared_from_this(), _1, _2));
}

void TCPConnection::handle_read_message_size(const boost::system::error_code &ec, std::size_t n_bytes)
{
  if (m_stopping)
    return;

  if (!ec) {
    m_read_size = ntohs(m_read_size);

    BOOST_LOG_SEV(m_log, log::lvl::trace) << connection_string()
      << ": incoming message size = " << m_read_size;

    if (m_read_size == 0) {
      BOOST_LOG_SEV(m_log, log::lvl::error) << connection_string()
        << ": zero request_size received";
      send_message(MessageFactory::make_error_response(error_type::invalid_message_size));
      m_connection_manager.stop(shared_from_this());
      return;
    }

    m_read_buf.clear();
    m_read_buf.resize(m_read_size);
    start_read_message();
  } else {
    if (ec == boost::asio::error::eof) {
      BOOST_LOG_SEV(m_log, log::lvl::info) << connection_string()
        << ": connection closed by peer";
    }
    else if (!m_stopping) {
      BOOST_LOG_SEV(m_log, log::lvl::error) << connection_string()
        << ": error reading message size: " << ec.message() << ec;
    }
    m_connection_manager.stop(shared_from_this(), false);
  }
}

void TCPConnection::start_read_message()
{
  BOOST_LOG_SEV(m_log, log::lvl::trace) << connection_string()
    << ": reading message of size " << m_read_size;

  asio::async_read(m_socket, asio::buffer(m_read_buf),
      boost::bind(&TCPConnection::handle_read_message, shared_from_this(), _1, _2));
}

void TCPConnection::handle_read_message(const boost::system::error_code &ec, std::size_t n_bytes)
{
  if (!ec) {
    try {
      MessagePtr msg(Message::deserialize(m_read_buf));

      BOOST_LOG_SEV(m_log, log::lvl::debug) << connection_string()
        << ": received message = " << msg->get_info_string();

      m_connection_manager.dispatch_request(shared_from_this(), msg);
      start_read_message_size();
    } catch (const std::runtime_error &e) {
      BOOST_LOG_SEV(m_log, log::lvl::error) << connection_string()
        << ": error deserializing message: " << e.what();

      send_message(MessageFactory::make_error_response(error_type::invalid_message_type));
      m_connection_manager.stop(shared_from_this());
    }
  } else {
    if (m_socket.is_open() && !m_stopping) {
      BOOST_LOG_SEV(m_log, log::lvl::error) << connection_string()
        << ": error reading message: " << ec.message();
    }
    m_connection_manager.stop(shared_from_this());
  }
}

void TCPConnection::start_write_message()
{
  if (m_write_queue.empty()) {
    if (m_stopping) {
      stop(false);
    }
    return;
  }

  if (m_write_in_progress)
    return;

  m_write_in_progress = true;

  MessagePtr msg(m_write_queue.front());
  
  m_write_buf  = msg->serialize();
  m_write_size = htons(m_write_buf.size());

  boost::array<asio::const_buffer, 2> buffers =
  {
      asio::buffer(&m_write_size, 2),
      asio::buffer(m_write_buf)
  };

  asio::async_write(m_socket, buffers,
      boost::bind(&TCPConnection::handle_write_message, shared_from_this(), _1, _2));
}

void TCPConnection::handle_write_message(const boost::system::error_code &ec, std::size_t n_bytes)
{
  m_write_in_progress = false;
  if (!ec) {
    BOOST_LOG_SEV(m_log, log::lvl::trace) << connection_string()
      << ": sent message of type " << m_write_queue.front()->get_info_string();
    m_write_queue.pop_front();
    start_write_message();
  } else {
    if (m_socket.is_open()) {
      BOOST_LOG_SEV(m_log, log::lvl::error) << connection_string()
        << ": error writing message: " << ec.message();
    }
    m_connection_manager.stop(shared_from_this());
  }
}

std::string TCPConnection::connection_string() const
{
  return m_connection_string;
}

} // namespace mesycontrol
