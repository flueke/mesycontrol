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
    // Automatically give write access to the first client
    set_write_connection(c);
  } else {
    // Notify the newly connected client that it does not have write access
    c->send_message(MessageFactory::make_write_access_notification(false));
    // Also tell the client if it can acquire write access
    c->send_message(MessageFactory::make_can_acquire_write_access_notification(!m_write_connection));
  }
}

void TCPConnectionManager::stop(TCPConnectionPtr c, bool graceful)
{
  if (m_write_connection == c) {
    // The current writer disconnects
    set_write_connection(TCPConnectionPtr());
  }

  m_connections.erase(c);
  c->stop(graceful);
}

void TCPConnectionManager::stop_all(bool graceful)
{
  BOOST_LOG_SEV(m_log, log::lvl::debug) << "Stopping all connections";
  std::for_each(m_connections.begin(), m_connections.end(),
      boost::bind(&TCPConnection::stop, _1, graceful));
  m_connections.clear();
  set_write_connection(TCPConnectionPtr());
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

      if (request->type == message_type::request_set ||
          request->type == message_type::request_mirror_set) {
        /* Create an artificial read request on parameter set to notify clients
         * about the updated memory value. */

        MessagePtr read_request(MessageFactory::make_read_request(
              request->bus, request->dev, request->par,
              request->type == message_type::request_mirror_set));

        m_mrc1_queue.queue_request(read_request,
            boost::bind(&TCPConnectionManager::handle_read_after_set,
              this, _1, _2));
      }
    }
  } else {
    MessagePtr response;
    bool stop_connection = false;

    switch (request->type) {
      case message_type::request_has_write_access:
        response = MessageFactory::make_bool_response(connection == m_write_connection);
        break;

      case message_type::request_acquire_write_access:
      case message_type::request_force_write_access:
        response = MessageFactory::make_bool_response(!m_write_connection
            || request->type == message_type::request_force_write_access);

        if (response->bool_value) {
          set_write_connection(connection);
        }

        break;

      case message_type::request_release_write_access:
        response = MessageFactory::make_bool_response(m_write_connection == connection);

        if (response->bool_value) {
          set_write_connection(TCPConnectionPtr());
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
        stop_connection = true;
    }

    if (response) {
      connection->send_message(response);
      if (stop_connection)
        stop(connection);
    }
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

void TCPConnectionManager::handle_read_after_set(
    const MessagePtr &request, const MessagePtr &response)
{
  if (response->type == message_type::response_read ||
      response->type == message_type::response_mirror_read) {

    send_to_all(MessageFactory::make_parameter_set_notification(
          response->bus, response->dev, response->par, response->val,
          response->type == message_type::response_mirror_read));
  }
}

void TCPConnectionManager::set_write_connection(const TCPConnectionPtr &connection)
{
  if ((!m_write_connection && !connection)
      || (m_write_connection == connection))
    return;

  const std::string old_writer_info(m_write_connection
      ? m_write_connection->connection_string()
      : std::string("<none>"));

  const std::string new_writer_info(connection
      ? connection->connection_string()
      : std::string("<none>"));

  if (m_write_connection) {
    // notify the old writer that it lost write access
    m_write_connection->send_message(MessageFactory::make_write_access_notification(false));
  }

  m_write_connection = connection;

  if (m_write_connection) {
    // notify the new writer that it gained write access
    m_write_connection->send_message(MessageFactory::make_write_access_notification(true));
  }

  // tell everyone else if write access is available
  send_to_all_except(m_write_connection,
      MessageFactory::make_can_acquire_write_access_notification(!m_write_connection));

  BOOST_LOG_SEV(m_log, log::lvl::info) << "Write access changed from "
    << old_writer_info << " to " << new_writer_info;
}

} // namespace mesycontrol
