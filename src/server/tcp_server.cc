#include <boost/bind.hpp>
#include <boost/make_shared.hpp>
#include "tcp_server.h"

namespace mesycontrol
{

TCPServer::TCPServer(boost::asio::io_service &io_service,
    boost::asio::ip::tcp::endpoint endpoint, RequestHandler request_handler)
  : m_io_service(io_service)
  , m_acceptor(io_service)
  , m_connection_manager()
  , m_new_connection()
  , m_request_handler(request_handler)
{
  m_acceptor.open(endpoint.protocol());
  m_acceptor.set_option(boost::asio::ip::tcp::acceptor::reuse_address(true));

  /* Try to enable IPv4 for IPv6 endpoints. */
  if (endpoint.protocol() == boost::asio::ip::tcp::v6()) {
    boost::system::error_code ignored_ec;
    m_acceptor.set_option(boost::asio::ip::v6_only(false), ignored_ec);
  }

  m_acceptor.bind(endpoint);
  m_acceptor.listen();

  start_accept();
}

TCPServer::~TCPServer()
{
  stop();
}

void TCPServer::stop()
{
  std::cerr << __PRETTY_FUNCTION__ << std::endl;
  m_acceptor.close();
  m_connection_manager.stop_all();
}

void TCPServer::start_accept()
{
  m_new_connection = boost::make_shared<TCPConnection>(
      boost::ref(m_io_service), boost::ref(m_connection_manager), m_request_handler);

  m_acceptor.async_accept(m_new_connection->socket(),
      boost::bind(&TCPServer::handle_accept, this,
        boost::asio::placeholders::error));
}

void TCPServer::handle_accept(const boost::system::error_code &ec)
{
  // Check whether the server was stopped by a signal before this completion
  // handler had a chance to run.
  if (!m_acceptor.is_open()) {
    return;
  }

  if (!ec) {
    m_connection_manager.start(m_new_connection);
  } else {
    std::cerr << "TCPServer::handle_accept: error: " << ec.message() << std::endl;
  }

  start_accept();
}

} // namespace mesycontrol
