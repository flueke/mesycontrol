#include <algorithm>
#include <boost/bind.hpp>
#include <boost/log/trivial.hpp>
#include "tcp_connection_manager.h"

namespace mesycontrol
{

TCPConnectionManager::TCPConnectionManager(MRC1RequestQueue &mrc1_queue)
  : m_mrc1_queue(mrc1_queue)
  , m_log(log::keywords::channel="TCPConnectionManager")
{}

void TCPConnectionManager::start(TCPConnectionPtr c)
{
  m_connections.insert(c);
  c->start();

  if (m_connections.size() == 1) {
    m_write_connection = c;
    c->send_message(MessageFactory::make_write_access_notification(true));
  } else {
    c->send_message(MessageFactory::make_write_access_notification(false));
  }
}

void TCPConnectionManager::stop(TCPConnectionPtr c)
{
  m_connections.erase(c);
  c->stop();

  if (m_write_connection == c) {
    m_write_connection.reset();
    send_to_all(MessageFactory::make_can_acquire_write_access_notification(true));
  }
}

void TCPConnectionManager::stop_all()
{
  std::for_each(m_connections.begin(), m_connections.end(),
      boost::bind(&TCPConnection::stop, _1));
  m_connections.clear();
  m_write_connection.reset();
}

void TCPConnectionManager::dispatch_request(const TCPConnectionPtr &connection, const MessagePtr &request)
{
  if (request->is_mrc1_command()) {
    if (request->is_mrc1_write_command() && connection != m_write_connection) {
      connection->send_message(MessageFactory::make_error_response(error_type::permission_denied));
    } else {
      m_mrc1_queue.queue_request(request,
          boost::bind(&TCPConnectionManager::handle_mrc1_response,
            this, connection, _1, _2));
    }
  } else {
    MessagePtr response;

    switch (request->type) {
      case message_type::request_has_write_access:
        response = MessageFactory::make_bool_response(connection == m_write_connection);
        break;

      case message_type::request_acquire_write_access:
        response = MessageFactory::make_bool_response(!m_write_connection);

        if (response->bool_value) {
          m_write_connection = connection;
          send_to_all_except(m_write_connection, MessageFactory::make_can_acquire_write_access_notification(false));
        }
        break;

      case message_type::request_release_write_access:
        response = MessageFactory::make_bool_response(m_write_connection == connection);

        if (response->bool_value) {
          m_write_connection.reset();
          send_to_all(MessageFactory::make_can_acquire_write_access_notification(true));
        }
        break;

      case message_type::request_in_silent_mode:
        response = MessageFactory::make_bool_response(m_mrc1_queue.get_mrc1_connection()->is_silenced());
        break;

      case message_type::request_set_silent_mode:
        response = MessageFactory::make_bool_response(m_write_connection == connection);

        if (response->bool_value) {
          m_mrc1_queue.get_mrc1_connection()->set_silenced(request->bool_value);
          send_to_all(MessageFactory::make_silent_mode_notification(request->bool_value));
        }
        break;

      default:
        /* Error: a response_* or notify_* message was received. */
        response = MessageFactory::make_error_response(error_type::invalid_message_type);
    }

    if (response)
      connection->send_message(response);
  }
}

void TCPConnectionManager::send_to_all(const MessagePtr &msg)
{
  std::for_each(m_connections.begin(), m_connections.end(),
      boost::bind(&TCPConnection::send_message, _1, msg));
}

void TCPConnectionManager::send_to_all_except(const TCPConnectionPtr &connection, const MessagePtr &msg)
{
  std::set<TCPConnectionPtr> connections(m_connections);
  connections.erase(connection);

  std::for_each(connections.begin(), connections.end(),
      boost::bind(&TCPConnection::send_message, _1, msg));
}

void TCPConnectionManager::handle_mrc1_response(const TCPConnectionPtr &connection,
    const MessagePtr &request, const MessagePtr &response)
{
  connection->send_message(response);

  if (response->type == message_type::response_set
      || response->type == message_type::response_mirror_set) {

    send_to_all_except(connection,
        MessageFactory::make_parameter_set_notification(
          response->bus, response->dev, response->par, response->val,
          response->type == message_type::response_mirror_set));
  }
}

} // namespace mesycontrol
