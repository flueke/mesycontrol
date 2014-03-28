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

TCPConnection::TCPConnection(
    boost::asio::io_service &io_service,
    TCPConnectionManager &manager,
    RequestHandler request_handler)
  : socket_(io_service)
  , connection_manager_(manager)
  , request_handler_(request_handler)
{
}

TCPConnection::~TCPConnection()
{
  stop();
}

void TCPConnection::start()
{
  static boost::format fmt("%1%:%2%");
  m_connection_string = boost::str(fmt
      % socket_.remote_endpoint().address().to_string()
      % socket_.remote_endpoint().port());

  BOOST_LOG_TRIVIAL(info) << "New connection from " << connection_string();

  socket_.set_option(asio::ip::tcp::no_delay(true));
  start_read_request_size();
}

void TCPConnection::stop()
{
  if (socket_.is_open()) {
    BOOST_LOG_TRIVIAL(info) << "Closing connection from " << connection_string();
    socket_.close();
  }
}

boost::asio::ip::tcp::socket &TCPConnection::socket()
{
  return socket_;
}

void TCPConnection::start_read_request_size()
{
  BOOST_LOG_TRIVIAL(debug) << connection_string() << ": reading request size";

  asio::async_read(socket_, asio::buffer(&request_size_, 2),
      boost::bind(&TCPConnection::handle_read_request_size, shared_from_this(), _1, _2));
}

void TCPConnection::handle_read_request_size(const boost::system::error_code &ec, std::size_t n_bytes)
{
  if (!ec) {
    request_size_ = ntohs(request_size_);
    BOOST_LOG_TRIVIAL(debug) << connection_string() << ": request size = " << request_size_;

    if (request_size_ == 0) {
      BOOST_LOG_TRIVIAL(error) << connection_string()
        << ": zero request size received. Closing connection";
      connection_manager_.stop(shared_from_this());
      return;
    }

    request_buf_.clear();
    request_buf_.resize(request_size_);
    start_read_request();
  } else {
    BOOST_LOG_TRIVIAL(error) << connection_string()
      << ": error reading request size: " << ec.message();
    connection_manager_.stop(shared_from_this());
  }
}

void TCPConnection::start_read_request()
{
  BOOST_LOG_TRIVIAL(debug) << connection_string() << ": reading request";

  asio::async_read(socket_, asio::buffer(request_buf_),
      boost::bind(&TCPConnection::handle_read_request, shared_from_this(), _1, _2));
}

void TCPConnection::handle_read_request(const boost::system::error_code &ec, std::size_t n_bytes)
{
  if (!ec) {
    try {
      MessagePtr msg(Message::deserialize(request_buf_));
      BOOST_LOG_TRIVIAL(info) << connection_string() << ": request read; type = " << msg->type;
      request_handler_(msg, boost::bind(&TCPConnection::response_ready_callback,
            shared_from_this(), _1, _2));
    } catch (const std::runtime_error &) {
      BOOST_LOG_TRIVIAL(error) << connection_string()
        << ": could not deserialize request; sending error response";

      response_buf_  = Message::make_error_response(error_type::invalid_type)->serialize();
      response_size_ = htons(response_buf_.size());
      start_write_response();
    }
  } else {
    BOOST_LOG_TRIVIAL(error) << connection_string()
      << ": error reading request: " << ec.message();
    connection_manager_.stop(shared_from_this());
  }
}

void TCPConnection::response_ready_callback(const MessagePtr &request, const MessagePtr &reply)
{
  BOOST_LOG_TRIVIAL(info) << connection_string()
    << ": sending response of type " << static_cast<int>(reply->type);

  response_buf_  = reply->serialize();
  response_size_ = htons(response_buf_.size());
  start_write_response();
}

void TCPConnection::start_write_response()
{
  boost::array<asio::const_buffer, 2> buffers =
  {
      asio::buffer(&response_size_, 2),
      asio::buffer(response_buf_)
  };

  asio::async_write(socket_, buffers,
      boost::bind(&TCPConnection::handle_write_response, shared_from_this(), _1, _2));
}

void TCPConnection::handle_write_response(const boost::system::error_code &ec, std::size_t n_bytes)
{
  if (!ec) {
    start_read_request_size();
  } else {
    BOOST_LOG_TRIVIAL(error) << connection_string()
      << ": error writing response: " << ec.message();
    connection_manager_.stop(shared_from_this());
  }
}

std::string TCPConnection::connection_string() const
{
  return m_connection_string;
}

} // namespace mesycontrol
