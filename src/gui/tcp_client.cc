#include "tcp_client.h"
#include <iostream>
#include <boost/bind.hpp>

namespace asio = boost::asio;
using asio::ip::tcp;

TCPClient::TCPClient(asio::io_service &io_service)
  : io_service_(io_service)
  , resolver_(io_service)
  , socket_(io_service)
  , work_(new asio::io_service::work(io_service))
{}

void TCPClient::connect_to(const std::string &hostname, const std::string &service_or_port)
{
  disconnect();

  tcp::resolver::query query(tcp::v4(), hostname, service_or_port);
  resolver_.async_resolve(query,
      boost::bind(&TCPClient::handle_resolve, shared_from_this(), _1, _2));
}

void TCPClient::handle_resolve(const boost::system::error_code& ec,
      tcp::resolver::iterator endpoint_iterator)
{
  if (!ec) {
    boost::system::error_code ec;
    tcp::resolver::iterator endpoint = asio::connect(socket_, endpoint_iterator, ec);
    handle_connect(ec, endpoint);
  } else {
    std::cout << "Resolve error: " << ec.message() << std::endl;
  }
}

void TCPClient::handle_connect(const boost::system::error_code &ec, tcp::resolver::iterator endpoint)
{
  if (!ec && socket_.is_open() && endpoint != tcp::resolver::iterator()) {
    std::cout << "Connected!" << std::endl;
    socket_.set_option(asio::ip::tcp::no_delay(true));
    start_write_request();
  } else {
    socket_.close();
    std::cout << "Could not connect:" << ec.message() << std::endl;
  }
}

void TCPClient::queue_request(protocol::Message request, ResponseHandler response_handler)
{
  bool was_empty(requests_.empty());
  requests_.push_back(std::make_pair(request, response_handler));
  if (was_empty) {
    start_write_request();
  }
}

void TCPClient::start_write_request()
{
  if (requests_.empty())
    return;

  request_buf_  = requests_.front().first.serialize();
  request_size_ = htons(request_buf_.size());

  boost::array<asio::const_buffer, 2> buffers =
  {
    asio::buffer(&request_size_, 2),
    asio::buffer(request_buf_)
  };

  asio::async_write(socket_, buffers,
      boost::bind(&TCPClient::handle_write_request, shared_from_this(), _1, _2));
}

void TCPClient::handle_write_request(const boost::system::error_code &ec, size_t n_bytes)
{
  if (!ec) {
    start_read_response_size();
  } else {
    requests_.front().second(requests_.front().first, protocol::Message::make_error_response(protocol::mrc_comm_error));
    requests_.pop_front();
    std::cout << "Error: " << ec.message() << std::endl;
    disconnect();
  }
}

void TCPClient::start_read_response_size()
{
  asio::async_read(socket_, asio::buffer(&response_size_, 2),
      boost::bind(&TCPClient::handle_read_response_size, shared_from_this(), _1, _2));
}

void TCPClient::handle_read_response_size(const boost::system::error_code &ec, size_t n_bytes)
{
  if (!ec) {
    response_size_ = ntohs(response_size_);
    response_buf_.clear();
    std::cout << "Expected response size = " << response_size_ << std::endl;
    response_buf_.resize(response_size_);
    start_read_response();
  } else {
    requests_.front().second(requests_.front().first, protocol::Message::make_error_response(protocol::mrc_comm_error));
    requests_.pop_front();
    std::cout << "Error: " << ec.message() << std::endl;
    disconnect();
  }
}

void TCPClient::start_read_response()
{
  asio::async_read(socket_, asio::buffer(response_buf_),
      boost::bind(&TCPClient::handle_read_response, shared_from_this(), _1, _2));
}

void TCPClient::handle_read_response(const boost::system::error_code &ec, size_t n_bytes)
{
  if (!ec) {
    protocol::Message msg(protocol::Message::deserialize(response_buf_));
    requests_.front().second(requests_.front().first, msg);
    requests_.pop_front();
    start_write_request();
  } else {
    requests_.front().second(requests_.front().first, protocol::Message::make_error_response(protocol::mrc_comm_error));
    requests_.pop_front();
    std::cout << "Error: " << ec.message() << std::endl;
    disconnect();
  }
}
