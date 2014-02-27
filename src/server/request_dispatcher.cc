#include <boost/bind.hpp>
#include "request_dispatcher.h"

namespace mesycontrol
{

RequestDispatcher::RequestDispatcher(
    const boost::shared_ptr<MRC1Connection> &mrc1_connection):
  m_mrc1_connection(mrc1_connection)
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

  if (!m_mrc1_connection->is_running()) {
    std::cerr << __PRETTY_FUNCTION__ << ": mrc connection is not running!" << std::endl;
    handle_mrc1_response(m_mrc1_request_queue.front().first, Message::make_error_response(error_type::mrc_connect_error));
  } else {
    std::cerr << __PRETTY_FUNCTION__ << ": calling mrc write command" << std::endl;
    m_mrc1_connection->write_command(m_mrc1_request_queue.front().first,
        boost::bind(&RequestDispatcher::handle_mrc1_response, this, _1, _2));
  }
}

} // namespace mesycontrol
