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
    BOOST_LOG_SEV(m_log, log::lvl::debug)
      << "starting poll cycle containing " << m_set.size() << " items";
  }

  m_set_iter = m_set.begin();
  poll_next();
}

void Poller::stop_cycle()
{
  BOOST_LOG_SEV(m_log, log::lvl::info) << "stopping poll cycle";
  m_set_iter = m_set.end();
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
  BOOST_LOG_SEV(m_log, log::lvl::debug) << "notify_cycle_complete: notifying handlers";

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

} // namespace mesycontrol
