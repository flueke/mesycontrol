#include <boost/bind.hpp>
#include <boost/make_shared.hpp>
#include "tcp_server.h"

namespace mesycontrol
{

TCPServer::TCPServer(boost::asio::io_service &io_service,
    boost::asio::ip::tcp::endpoint endpoint, RequestHandler request_handler)
  : io_service_(io_service)
  , acceptor_(io_service)
  , connection_manager_()
  , new_connection_()
  , request_handler_(request_handler)
{
  acceptor_.open(endpoint.protocol());
  acceptor_.set_option(boost::asio::ip::tcp::acceptor::reuse_address(true));
  acceptor_.bind(endpoint);
  acceptor_.listen();

  start_accept();
}

TCPServer::~TCPServer()
{
}

void TCPServer::stop()
{
  std::cerr << __PRETTY_FUNCTION__ << std::endl;
  acceptor_.close();
  connection_manager_.stop_all();
}

void TCPServer::start_accept()
{
  new_connection_ = boost::make_shared<TCPConnection>(
      boost::ref(io_service_), boost::ref(connection_manager_), request_handler_);

  acceptor_.async_accept(new_connection_->socket(),
      boost::bind(&TCPServer::handle_accept, this,
        boost::asio::placeholders::error));
}

void TCPServer::handle_accept(const boost::system::error_code &ec)
{
  // Check whether the server was stopped by a signal before this completion
  // handler had a chance to run.
  if (!acceptor_.is_open()) {
    return;
  }

  if (!ec) {
    connection_manager_.start(new_connection_);
  } else {
    std::cerr << "TCPServer::handle_accept: error: " << ec.message() << std::endl;
  }

  start_accept();
}

} // namespace mesycontrol
