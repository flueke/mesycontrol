#ifndef __MINGW32__
#include <arpa/inet.h>
#endif
#include <boost/bind.hpp>
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
  std::cerr << __PRETTY_FUNCTION__ << std::endl;
}

void TCPConnection::start()
{
  socket_.set_option(asio::ip::tcp::no_delay(true));
  start_read_request_size();
}

void TCPConnection::stop()
{
  std::cerr << __PRETTY_FUNCTION__ << std::endl;
  socket_.close();
}

boost::asio::ip::tcp::socket &TCPConnection::socket()
{
  return socket_;
}

void TCPConnection::start_read_request_size()
{
  asio::async_read(socket_, asio::buffer(&request_size_, 2),
      boost::bind(&TCPConnection::handle_read_request_size, shared_from_this(), _1, _2));
}

void TCPConnection::handle_read_request_size(const boost::system::error_code &ec, std::size_t n_bytes)
{
  if (!ec) {
    request_size_ = ntohs(request_size_);
    std::cerr << __PRETTY_FUNCTION__ << "request_size = " << request_size_ << std::endl;
    request_buf_.clear();
    request_buf_.resize(request_size_);
    start_read_request();
  } else {
    connection_manager_.stop(shared_from_this());
  }
}

void TCPConnection::start_read_request()
{
  asio::async_read(socket_, asio::buffer(request_buf_),
      boost::bind(&TCPConnection::handle_read_request, shared_from_this(), _1, _2));
}

void TCPConnection::handle_read_request(const boost::system::error_code &ec, std::size_t n_bytes)
{
  if (!ec) {
    MessagePtr msg(Message::deserialize(request_buf_));
    request_handler_(msg, boost::bind(&TCPConnection::response_ready_callback,
          shared_from_this(), _1, _2));
  } else {
    connection_manager_.stop(shared_from_this());
  }
}

void TCPConnection::response_ready_callback(const MessagePtr &request, const MessagePtr &reply)
{
  std::cout << __PRETTY_FUNCTION__ << "got reply of type " << static_cast<int>(reply->type) << std::endl;
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
    connection_manager_.stop(shared_from_this());
  }
}

} // namespace mesycontrol
