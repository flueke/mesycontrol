#include <algorithm>
#include <boost/bind.hpp>
#include <boost/log/trivial.hpp>
#include <boost/make_shared.hpp>
#include "tcp_connection_manager.h"

namespace mesycontrol
{

TCPConnectionManager::TCPConnectionManager(MRC1RequestQueue &mrc1_queue)
  : m_mrc1_queue(mrc1_queue)
  , m_log(log::keywords::channel="TCPConnectionManager")
  , m_skip_read_after_set_response(false)
  , m_poller(mrc1_queue)
  , m_scanbus_poller(mrc1_queue)
{
  m_mrc1_queue.get_mrc1_connection()->register_status_change_callback(
      boost::bind(&TCPConnectionManager::handle_mrc1_status_change, this, _1, _2, _3, _4));

  m_poller.register_result_handler(boost::bind(
        &TCPConnectionManager::handle_poll_cycle_complete, this, _1));

  m_scanbus_poller.register_result_handler(boost::bind(
        &TCPConnectionManager::handle_scanbus_poll_complete, this, _1));
}

void TCPConnectionManager::start(TCPConnectionPtr c)
{
  m_connections.insert(c);
  c->start();

  c->send_message(MessageFactory::make_mrc_status_notification(
        m_mrc1_queue.get_mrc1_connection()->get_status()));

  c->send_message(MessageFactory::make_silent_mode_notification(
        m_mrc1_queue.get_mrc1_connection()->is_silenced()));

  if (m_connections.size() == 1) {
    // Automatically give write access to the first client
    set_write_connection(c);

    m_poller.start();
    m_scanbus_poller.start();
  } else {
    // Notify the newly connected client that it does not have write access
    c->send_message(MessageFactory::make_write_access_notification(false, !m_write_connection));
  }
}

void TCPConnectionManager::stop(TCPConnectionPtr c, bool graceful)
{
  if (m_write_connection == c) {
    // The current writer disconnects. If there's only one connection left make
    // it the new writer, otherwise make no connection a writer.
    set_write_connection(m_connections.size() == 1 ?
        *(m_connections.begin()) : TCPConnectionPtr());
  }

  m_connections.erase(c);
  m_poller.remove_poller(c);
  c->stop(graceful);

  if (m_connections.empty()) {
    m_poller.stop();
    m_scanbus_poller.stop();
  }
}

void TCPConnectionManager::stop_all(bool graceful)
{
  BOOST_LOG_SEV(m_log, log::lvl::debug) << "Stopping all connections";

  std::for_each(m_connections.begin(), m_connections.end(),
      boost::bind(&TCPConnection::stop, _1, graceful));

  std::for_each(m_connections.begin(), m_connections.end(),
      boost::bind(&Poller::remove_poller, &m_poller, _1));

  m_connections.clear();
  set_write_connection(TCPConnectionPtr());

  m_poller.stop();
  m_scanbus_poller.stop();
}

void TCPConnectionManager::dispatch_request(const TCPConnectionPtr &connection, const MessagePtr &request)
{
  if (is_mrc1_command(request)) {
    if (is_mrc1_write_command(request) && connection != m_write_connection) {
      connection->send_message(MessageFactory::make_error_response(proto::ResponseError::PERMISSION_DENIED));
    } else {
      if (request->type() == proto::Message::REQ_SET) {
        m_mrc1_queue.queue_request(request,
            boost::bind(&TCPConnectionManager::handle_set_response,
              this, connection, _1, _2));

        /* Create an extra read request on parameter set to get the
         * updated memory value. */
        MessagePtr read_request(MessageFactory::make_read_request(
              request->request_set().bus(),
              request->request_set().dev(),
              request->request_set().par(),
              request->request_set().mirror()));

        m_mrc1_queue.queue_request(read_request,
            boost::bind(&TCPConnectionManager::handle_read_after_set,
              this, connection, _1, _2));
      } else {
        m_mrc1_queue.queue_request(request,
            boost::bind(&TCPConnectionManager::handle_mrc1_response,
              this, connection, _1, _2));
      }
    }
  } else {
    MessagePtr response;
    bool stop_connection = false;

    switch (request->type()) {
      case proto::Message::REQ_HAS_WRITE_ACCESS:
        response = MessageFactory::make_bool_response(connection == m_write_connection);
        break;

      case proto::Message::REQ_ACQUIRE_WRITE_ACCESS:
        {
          bool force(request->request_acquire_write_access().force());
          bool can_acquire(!m_write_connection || force);

          if (can_acquire) {
            set_write_connection(connection);
          }

          response = MessageFactory::make_bool_response(can_acquire);
        }

        break;

      case proto::Message::REQ_RELEASE_WRITE_ACCESS:
        {
          bool may_release(m_write_connection == connection);

          if (may_release) {
            set_write_connection(TCPConnectionPtr());
          }

          response = MessageFactory::make_bool_response(may_release);
        }
        break;

      case proto::Message::REQ_IS_SILENCED:
        response = MessageFactory::make_bool_response(m_mrc1_queue.get_mrc1_connection()->is_silenced());
        break;

      case proto::Message::REQ_SET_SILENCED:
        {
          bool may_set(m_write_connection == connection);
          bool silenced(request->request_set_silenced().silenced());

          if (may_set) {
            m_mrc1_queue.get_mrc1_connection()->set_silenced(silenced);
            send_to_all(MessageFactory::make_silent_mode_notification(silenced));

            if (silenced) {
              m_poller.stop();
              m_scanbus_poller.stop();
            } else {
              m_poller.start();
              m_scanbus_poller.start();
            }
          }

          response = MessageFactory::make_bool_response(may_set);
        }

        break;

      case proto::Message::REQ_MRC_STATUS:
        response = MessageFactory::make_mrc_status_response(
            m_mrc1_queue.get_mrc1_connection()->get_status());
        break;

      case proto::Message::REQ_SET_POLL_ITEMS:
        {
          PollItems items;

          const proto::RequestSetPollItems &poll_request(request->request_set_poll_items());

          BOOST_LOG_SEV(m_log, log::lvl::info)
            << connection->connection_string()
            << ": received " << poll_request.items_size() << " poll items";

          for (int i=0; i<poll_request.items_size(); ++i) {
            const proto::RequestSetPollItems::PollItem &proto_item(poll_request.items(i));

            // Expand the protocol poll item into individual parameters.
            for (boost::uint32_t par=proto_item.par();
                par<proto_item.par()+proto_item.count(); ++par) {

              items.push_back(PollItem(proto_item.bus(), proto_item.dev(), par));
            }
          }

          m_poller.set_poll_items(connection, items);

          response = MessageFactory::make_bool_response(true);
        }
        break;

      default:
        BOOST_LOG_SEV(m_log, log::lvl::error) << connection->connection_string()
          << ": invalid message received: " << get_message_info(request);
        response = MessageFactory::make_error_response(proto::ResponseError::INVALID_TYPE);
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
}

void TCPConnectionManager::handle_set_response(const TCPConnectionPtr &connection,
    const MessagePtr &request, const MessagePtr &response)
{
  /* Only pass error messages on to the connection. The actual reponse to the
   * set command will be sent by handle_read_after_set(). */
  if (response->type() == proto::Message::RESP_ERROR) {
    connection->send_message(response);
    m_skip_read_after_set_response = true; // Don't send a response to the read_after_set request
  }
}

void TCPConnectionManager::handle_read_after_set(const TCPConnectionPtr &connection,
    const MessagePtr &request, const MessagePtr &response)
{
  if (m_skip_read_after_set_response) {
    m_skip_read_after_set_response = false;
    return;
  }

  /* Send a set/mirror_set response to the client that originally sent the set
   * request. */
  MessagePtr msg(MessageFactory::make_set_response(
        response->response_read().bus(),
        response->response_read().dev(),
        response->response_read().par(),
        response->response_read().val(),
        response->response_read().mirror()));

  connection->send_message(msg);

  /* Notify other clients that a parameter has been set. */
  msg->set_type(proto::Message::NOTIFY_SET);
  send_to_all_except(connection, msg);

  if (!response->response_read().mirror()) {
    /* Tell the poller that a parameter has been set. */
    m_poller.notify_parameter_changed(
        response->response_read().bus(),
        response->response_read().dev(),
        response->response_read().par(),
        response->response_read().val());
  }
}

void TCPConnectionManager::handle_mrc1_status_change(const proto::MRCStatus::Status &status,
    const std::string &info, const std::string &version, bool has_read_multi)
{
  send_to_all(MessageFactory::make_mrc_status_notification(status, info, version,
        has_read_multi));

  if (status == proto::MRCStatus::RUNNING && !m_connections.empty()) {
    m_poller.start();
    m_scanbus_poller.start();
  } else {
    m_poller.stop();
    m_scanbus_poller.stop();
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
    m_write_connection->send_message(MessageFactory::make_write_access_notification(false, false));
  }

  m_write_connection = connection;

  if (m_write_connection) {
    // notify the new writer that it gained write access
    m_write_connection->send_message(MessageFactory::make_write_access_notification(true, false));
  }

  // tell everyone else if write access is available
  send_to_all_except(m_write_connection,
      MessageFactory::make_write_access_notification(false, !m_write_connection));

  BOOST_LOG_SEV(m_log, log::lvl::info) << "Write access changed from "
    << old_writer_info << " to " << new_writer_info;
}

void TCPConnectionManager::handle_poll_cycle_complete(
    const Poller::ResultType &result)
{
  MessagePtr m(boost::make_shared<proto::Message>());
  m->set_type(proto::Message::NOTIFY_POLLED_ITEMS);

  for (Poller::ResultType::const_iterator it=result.begin();
      it!=result.end(); ++it) {

    proto::NotifyPolledItems::PollResult *pr(
        m->mutable_notify_polled_items()->add_items());

    pr->set_bus(it->bus);
    pr->set_dev(it->dev);
    pr->set_par(it->par);
    pr->add_values(it->val);
  }

  send_to_all(m);
}

void TCPConnectionManager::handle_scanbus_poll_complete(
    const MessagePtr &scanbus_notification)
{
  send_to_all(scanbus_notification);
}

} // namespace mesycontrol
