#include <boost/bind.hpp>
#include <chrono>
#include <boost/date_time/posix_time/posix_time.hpp>
#include <boost/log/trivial.hpp>
#include "mrc1_request_queue.h"
#include "protocol.h"

namespace mesycontrol
{

const boost::asio::steady_timer::duration
  MRC1RequestQueue::default_retry_timeout(std::chrono::seconds(1));

MRC1RequestQueue::MRC1RequestQueue(const boost::shared_ptr<MRC1Connection> &mrc1_connection):
  m_mrc1_connection(mrc1_connection),
  m_retry_timer(mrc1_connection->get_io_service()),
  m_log(log::keywords::channel="MRC1RequestQueue"),
  m_command_in_progress(false)
{
  set_retry_timeout(default_retry_timeout);
}

void MRC1RequestQueue::queue_request(const MessagePtr &request, ResponseHandler response_handler)
{
  if (!is_mrc1_command(request)) {
    BOOST_THROW_EXCEPTION(std::runtime_error("Given request is not a MRC1 command"));
  }

  m_request_queue.push_back(std::make_pair(request, response_handler));

  BOOST_LOG_SEV(m_log, log::lvl::trace)
    << "Queueing request " << get_message_info(request)
    << " (" << request
    << "), queue size=" << m_request_queue.size();

  try_send_mrc1_request();
}

void MRC1RequestQueue::try_send_mrc1_request()
{
  if (m_request_queue.empty()) {
    BOOST_LOG_SEV(m_log, log::lvl::trace) << "try_send_mrc1_request: Empty queue. Nothing to do";
    return;
  }

  if (m_command_in_progress) {
    BOOST_LOG_SEV(m_log, log::lvl::trace) << "try_send_mrc1_request: Command in progress (this)";
    return;
  }
  
  if (m_mrc1_connection->command_in_progress()) {
    BOOST_LOG_SEV(m_log, log::lvl::trace) << "try_send_mrc1_request: Command in progress (MRC1Connection)";
    return;
  }

  if (!m_mrc1_connection->is_running()) {
    if (m_mrc1_connection->get_status() == proto::MRCStatus::INITIALIZING) {
      BOOST_LOG_SEV(m_log, log::lvl::debug) << "MRC still initializing. Retrying later";
      m_retry_timer.expires_from_now(get_retry_timeout());
      m_retry_timer.async_wait(boost::bind(&MRC1RequestQueue::handle_retry_timer, this, _1));
      return;
    }

    proto::ResponseError::ErrorType et;

    switch (m_mrc1_connection->get_status()) {
      case proto::MRCStatus::CONNECT_FAILED:
        et = proto::ResponseError::CONNECT_ERROR;
        break;
      case proto::MRCStatus::INIT_FAILED:
        et = proto::ResponseError::COM_ERROR;
        break;
      case proto::MRCStatus::CONNECTING:
      case proto::MRCStatus::INITIALIZING:
        et = proto::ResponseError::CONNECTING;
        break;
      default:
        et = proto::ResponseError::UNKNOWN;
        break;
    }
    BOOST_LOG_SEV(m_log, log::lvl::error) << "MRC connection not running. Sending error response";
    handle_mrc1_response(m_request_queue.front().first, MessageFactory::make_error_response(et));
  } else {
    BOOST_LOG_SEV(m_log, log::lvl::trace)
      << "invoking MRC write_command(): "
      << get_message_info(m_request_queue.front().first)
      << "(" << m_request_queue.front().first << ")";

    m_mrc1_connection->write_command(m_request_queue.front().first,
        boost::bind(&MRC1RequestQueue::handle_mrc1_response, this, _1, _2));

    m_command_in_progress = true;
  }
}

void MRC1RequestQueue::handle_retry_timer(const boost::system::error_code &)
{
  try_send_mrc1_request();
}

void MRC1RequestQueue::handle_mrc1_response(const MessagePtr &request, const MessagePtr &response)
{
  BOOST_LOG_SEV(m_log, log::lvl::debug)
    << "handle_mrc1_response: req=" << get_message_info(request)
    << "(" << request << ")"
    << ", resp=" << get_message_info(response)
    << "(" << response << ")";

  m_request_queue.front().second(request, response);
  m_request_queue.pop_front();
  m_command_in_progress = false;
  try_send_mrc1_request();
}

}
