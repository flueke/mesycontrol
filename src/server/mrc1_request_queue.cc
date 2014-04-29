#include <boost/bind.hpp>
#include <boost/log/trivial.hpp>
#include "mrc1_request_queue.h"

namespace mesycontrol
{

const boost::asio::steady_timer::duration
  MRC1RequestQueue::default_retry_timeout(boost::chrono::seconds(1));

MRC1RequestQueue::MRC1RequestQueue(const boost::shared_ptr<MRC1Connection> &mrc1_connection):
  m_mrc1_connection(mrc1_connection),
  m_retry_timer(mrc1_connection->get_io_service()),
  m_log(log::keywords::channel="MRC1RequestQueue")
{
  set_retry_timeout(default_retry_timeout);
}

void MRC1RequestQueue::queue_request(const MessagePtr &request, ResponseHandler response_handler)
{
  if (!request->is_mrc1_command()) {
    BOOST_THROW_EXCEPTION(std::runtime_error("Given request is not a MRC1 command"));
  }
  m_request_queue.push_back(std::make_pair(request, response_handler));
  try_send_mrc1_request();
}

void MRC1RequestQueue::try_send_mrc1_request()
{
  if (m_request_queue.empty()) {
    BOOST_LOG_SEV(m_log, log::lvl::trace) << "Empty queue. Nothing to do";
    return;
  }
  
  if (m_mrc1_connection->command_in_progress()) {
    BOOST_LOG_SEV(m_log, log::lvl::trace) << "Command in progress";
    return;
  }

  if (!m_mrc1_connection->is_running()) {
    if (m_mrc1_connection->get_status() == MRC1Connection::initializing) {
      BOOST_LOG_SEV(m_log, log::lvl::debug) << "MRC still initializing. Retrying later";
      m_retry_timer.expires_from_now(get_retry_timeout());
      m_retry_timer.async_wait(boost::bind(&MRC1RequestQueue::handle_retry_timer, this, _1));
      return;
    }

    error_type::ErrorType et;

    switch (m_mrc1_connection->get_status()) {
      case MRC1Connection::connect_failed:
        et = error_type::mrc_connect_error;
        break;
      case MRC1Connection::init_failed:
        et = error_type::mrc_comm_error;
        break;
      default:
        et = error_type::unknown_error;
        break;
    }
    BOOST_LOG_SEV(m_log, log::lvl::error) << "MRC connection not running. Sending error response";
    handle_mrc1_response(m_request_queue.front().first, MessageFactory::make_error_response(et));
  } else {
    BOOST_LOG_SEV(m_log, log::lvl::trace) << "invoking MRC write_command()";
    m_mrc1_connection->write_command(m_request_queue.front().first,
        boost::bind(&MRC1RequestQueue::handle_mrc1_response, this, _1, _2));
  }
}

void MRC1RequestQueue::handle_retry_timer(const boost::system::error_code &)
{
  try_send_mrc1_request();
}

void MRC1RequestQueue::handle_mrc1_response(const MessagePtr &request, const MessagePtr &response)
{
  m_request_queue.front().second(request, response);
  m_request_queue.pop_front();
  try_send_mrc1_request();
}

}
