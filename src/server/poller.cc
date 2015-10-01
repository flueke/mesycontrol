#include <boost/bind.hpp>
#include "mrc1_request_queue.h"
#include "poller.h"

namespace mesycontrol
{

std::size_t hash_value(const PollItem &item)
{
  return item.bus + 10*item.dev + 100*item.par;
}

std::size_t hash_value(const PollResult &result)
{
  return hash_value(static_cast<const PollItem &>(result));
}

std::ostream &operator<<(std::ostream &os, const PollItems &items)
{
  PollItems::const_iterator it=items.begin();

  os << "PollItems(";

  while (it != items.end()) {
    os << "(" << it->bus << ", " << it->dev << ", " << it->par << ")";
    if ((++it) != items.end())
      os << ", ";
  }

  os << ")";

  return os;
}

std::ostream &operator<<(std::ostream &os, const PollResult &result)
{
  os << "PollResult("
    << result.bus << ", " << result.dev << ", " << result.par << ", " << result.val
    << ")";
  return os;
}

Poller::Poller(MRC1RequestQueue &mrc1_queue,
    boost::posix_time::time_duration min_interval)
  : m_log(log::keywords::channel="Poller")
  , m_queue(mrc1_queue)
  , m_set_iter(m_set.end())
  , m_timer(mrc1_queue.get_mrc1_connection()->get_io_service())
  , m_min_interval(min_interval)
  , m_stopping(false)
{
  m_queue.get_mrc1_connection()->register_status_change_callback(
      boost::bind(&Poller::handle_mrc1_status_change, this, _1, _2, _3, _4));
}

void Poller::set_poll_items(const TCPConnectionPtr &connection, const PollItems &items)
{
  BOOST_LOG_SEV(m_log, log::lvl::info)
    << "set_poll_items: " << connection->connection_string() << " -> " << items;

  m_map[connection] = items;
}

void Poller::remove_poller(const TCPConnectionPtr &connection)
{
  BOOST_LOG_SEV(m_log, log::lvl::info)
    << "remove_poller " << connection->connection_string();

  m_map.erase(connection);
}

void Poller::stop()
{
  BOOST_LOG_SEV(m_log, log::lvl::info) << "poller stopping";
  m_stopping = true;
  m_timer.cancel();
}

void Poller::notify_parameter_changed(
    boost::uint32_t bus,
    boost::uint32_t dev,
    boost::uint32_t par,
    boost::uint32_t val)
{
  PollResult res(bus, dev, par, val);

  ResultType::iterator it = m_result.find(res);

  if (it != m_result.end()) {
    const PollResult &old(*it);

    BOOST_LOG_SEV(m_log, log::lvl::info) << "updating polled param: "
      << old << " -> " << res;

    m_result.erase(it);
    m_result.insert(res);
  }
}

void Poller::handle_mrc1_status_change(const proto::MRCStatus::Status &status,
    const std::string &info, const std::string &version, bool has_read_multi)
{
  if (status == proto::MRCStatus::RUNNING) {
    start_cycle();
  } else {
    stop_cycle();
  }
}

void Poller::start_cycle()
{
  if (m_stopping)
    return;

  m_set.clear();
  m_result.clear();

  for (PollItemsMap::const_iterator it=m_map.begin(); it!=m_map.end(); ++it) {
    for (PollItems::const_iterator jt=it->second.begin(); jt!=it->second.end(); ++jt) {
      m_set.insert(*jt);
    }
  }

  if (m_set.size()) {
    BOOST_LOG_SEV(m_log, log::lvl::info)
      << "starting poll cycle containing " << m_set.size() << " items";
  }

  m_set_iter = m_set.begin();
  poll_next();
}

void Poller::stop_cycle()
{
  if (m_set_iter != m_set.end()) {
    BOOST_LOG_SEV(m_log, log::lvl::info) << "stopping poll cycle";
    m_set_iter = m_set.end();
  }
}

void Poller::poll_next()
{
  if (m_stopping)
    return;

  if (m_set_iter != m_set.end() && m_queue.size() == 0) {
    const PollItem &item(*m_set_iter);

    BOOST_LOG_SEV(m_log, log::lvl::debug)
      << "poll_next: queueing read request for ("
      << item.bus << "," << item.dev << "," << item.par << ")";

    m_queue.queue_request(
        MessageFactory::make_read_request(item.bus, item.dev, item.par),
        boost::bind(&Poller::handle_response, this, _1, _2)
        );
  } else {
    m_timer.expires_from_now(m_min_interval);
    m_timer.async_wait(boost::bind(&Poller::handle_timeout, this, _1));
  }
}

void Poller::handle_response(const MessagePtr &request, const MessagePtr &response)
{
  if (response->type() == proto::Message::RESP_READ) {

    BOOST_LOG_SEV(m_log, log::lvl::debug)
      << "handle_response: received read response. adding to poll result";

    m_result.insert(PollResult(
          response->response_read().bus(),
          response->response_read().dev(),
          response->response_read().par(),
          response->response_read().val()));

    ++m_set_iter;

    if (m_set_iter == m_set.end()) {
      notify_cycle_complete();
    } else {
      poll_next();
    }
  } else {
    BOOST_LOG_SEV(m_log, log::lvl::debug)
      << "handle_response: received non-read response. invoking poll_next()";
    poll_next();
  }
}

void Poller::notify_cycle_complete()
{
  BOOST_LOG_SEV(m_log, log::lvl::info) << "notify_cycle_complete: notifying handlers";

  for (std::vector<ResultHandler>::iterator it = m_result_handlers.begin();
      it != m_result_handlers.end(); ++it) {
    (*it)(m_result);
  }

  start_cycle();
}

void Poller::handle_timeout(const boost::system::error_code &ec)
{
  if (ec != boost::asio::error::operation_aborted &&
      m_timer.expires_at() <= boost::asio::deadline_timer::traits_type::now()) {

    if (m_set_iter != m_set.end()) {
      poll_next();
    } else {
      start_cycle();
    }
  }
}

ScanbusPoller::ScanbusPoller(MRC1RequestQueue &mrc1_queue,
    boost::posix_time::time_duration min_interval)
  : m_log(log::keywords::channel="ScanbusPoller")
  , m_queue(mrc1_queue)
  , m_timer(mrc1_queue.get_mrc1_connection()->get_io_service())
  , m_min_interval(min_interval)
  , m_suspended(false)
{
  m_queue.get_mrc1_connection()->register_status_change_callback(
      boost::bind(&ScanbusPoller::handle_mrc1_status_change, this, _1, _2, _3, _4));
}

void ScanbusPoller::stop()
{
  m_timer.cancel();
}

void ScanbusPoller::set_suspended(bool suspended)
{
  if (is_suspended() == suspended)
    return;

  m_suspended = suspended;

  if (is_suspended()) {
    BOOST_LOG_SEV(m_log, log::lvl::info) << "Scanbus polling suspended";
    m_timer.cancel();
  } else {
    BOOST_LOG_SEV(m_log, log::lvl::info) << "Scanbus polling resumed";
    m_timer.expires_from_now(boost::posix_time::milliseconds(0));
    m_timer.async_wait(boost::bind(&ScanbusPoller::handle_timeout, this, _1));
  }
}

void ScanbusPoller::handle_mrc1_status_change(const proto::MRCStatus::Status &status,
    const std::string &info, const std::string &version, bool has_read_multi)
{
  if (status == proto::MRCStatus::RUNNING && !is_suspended()) {
    m_timer.expires_from_now(boost::posix_time::milliseconds(0));
    m_timer.async_wait(boost::bind(&ScanbusPoller::handle_timeout, this, _1));
  } else {
    m_timer.cancel();
  }
}

void ScanbusPoller::handle_response(const MessagePtr &request, const MessagePtr &response)
{
  BOOST_LOG_SEV(m_log, log::lvl::info)
    << "req=" << get_message_info(request)
    << ", resp=" << get_message_info(response);

  BOOST_LOG_SEV(m_log, log::lvl::info)
    << "bus=" << response->scanbus_result().bus()
    << ", #entries=" << response->scanbus_result().entries_size();

  // Change message type from response to notification. Both use the
  // 'scanbus_result' member of the Message class.
  response->set_type(proto::Message::NOTIFY_SCANBUS);

  BOOST_LOG_SEV(m_log, log::lvl::debug) << "notifying result handlers";

  for (std::vector<ResultHandler>::iterator it = m_result_handlers.begin();
      it != m_result_handlers.end(); ++it) {
    (*it)(response);
  }

  m_timer.expires_from_now(m_min_interval);
  m_timer.async_wait(boost::bind(&ScanbusPoller::handle_timeout, this, _1));
}

void ScanbusPoller::handle_timeout(const boost::system::error_code &ec)
{
  if (ec != boost::asio::error::operation_aborted &&
      m_timer.expires_at() <= boost::asio::deadline_timer::traits_type::now()) {

    BOOST_LOG_SEV(m_log, log::lvl::debug) << "queueing scanbus requests";

    for (int i=0; i<2; ++i) {
      m_queue.queue_request(MessageFactory::make_scanbus_request(i),
          boost::bind(&ScanbusPoller::handle_response, this, _1, _2));
    }
  }
}

} // namespace mesycontrol
