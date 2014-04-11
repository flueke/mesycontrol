#include <boost/bind.hpp>
#include "request_dispatcher.h"

namespace mesycontrol
{

RequestDispatcher::RequestDispatcher(
    const boost::shared_ptr<MRC1Connection> &mrc1_connection):
  m_mrc1_connection(mrc1_connection),
  m_retry_timer(mrc1_connection->get_io_service())
{
}

void RequestDispatcher::dispatch(const MessagePtr &request, ResponseHandler response_handler)
{
  if (request->is_mrc1_command()) {
    m_mrc1_request_queue.push_back(std::make_pair(request, response_handler));
    std::cerr << __PRETTY_FUNCTION__ << " queue_size = " << m_mrc1_request_queue.size() << std::endl;
    try_send_mrc1_request();
  } else {
    dispatch_control_message(request, response_handler);
  }
}

/** TODO: implement master and silent mode */
void RequestDispatcher::dispatch_control_message(const MessagePtr &request, ResponseHandler response_handler)
{
  switch (request->type) {
    case message_type::request_is_master:
      response_handler(request, Message::make_bool_response(true));
      break;
    case message_type::request_acquire_master:
      response_handler(request, Message::make_bool_response(true));
      break;
    case message_type::request_in_silent_mode:
      response_handler(request, Message::make_bool_response(false));
      break;
    case message_type::request_set_silent_mode:
      response_handler(request, Message::make_bool_response(false));
      break;
    default:
      response_handler(request, Message::make_error_response(error_type::invalid_type));
      break;
  }
}

void RequestDispatcher::handle_mrc1_response(const MessagePtr &request, const MessagePtr &response)
{
  m_mrc1_request_queue.front().second(request, response);
  m_mrc1_request_queue.pop_front();
  std::cerr << __PRETTY_FUNCTION__ << " queue_size = " << m_mrc1_request_queue.size() << std::endl;
  try_send_mrc1_request();
}

void RequestDispatcher::try_send_mrc1_request()
{
  if (m_mrc1_request_queue.empty()) {
    std::cerr << __PRETTY_FUNCTION__ << ": queue is empty" << std::endl;
    return;
  }
  
  if (m_mrc1_connection->command_in_progress()) {
    std::cerr << __PRETTY_FUNCTION__ << ": mrc_command_in_progress" << std::endl;
    return;
  }

  if (m_mrc1_connection->get_status() == MRC1Connection::initializing) {
    std::cerr << __PRETTY_FUNCTION__ << ": MRC1Connection is still initializing. Retrying." << std::endl;
    m_retry_timer.expires_from_now(boost::chrono::seconds(1));
    m_retry_timer.async_wait(boost::bind(&RequestDispatcher::handle_retry_timer, this, _1));
    return;
  }

  if (!m_mrc1_connection->is_running()) {
    error_type::ErrorType et;

    switch (m_mrc1_connection->get_status()) {
      case MRC1Connection::connect_failed:
        et = error_type::mrc_connect_error;
        break;
      case MRC1Connection::initializing:
        et = error_type::mrc_initializing;
        break;
      case MRC1Connection::init_failed:
        et = error_type::mrc_comm_error;
        break;
      default:
        et = error_type::unknown_error;
        break;
    }
    std::cerr << __PRETTY_FUNCTION__ << ": mrc connection is not running!" << std::endl;
    handle_mrc1_response(m_mrc1_request_queue.front().first, Message::make_error_response(et));
  } else {
    std::cerr << __PRETTY_FUNCTION__ << ": calling mrc write command" << std::endl;
    std::cerr << __PRETTY_FUNCTION__ << ": message type = " << m_mrc1_request_queue.front().first->type << std::endl;
    std::cerr << __PRETTY_FUNCTION__ << ": message = " << m_mrc1_request_queue.front().first->get_mrc1_command_string() << std::endl;
    m_mrc1_connection->write_command(m_mrc1_request_queue.front().first,
        boost::bind(&RequestDispatcher::handle_mrc1_response, this, _1, _2));
  }
}

void RequestDispatcher::handle_retry_timer(const boost::system::error_code &)
{
  try_send_mrc1_request();
}

} // namespace mesycontrol
