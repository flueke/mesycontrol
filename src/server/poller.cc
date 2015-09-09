#include <boost/bind.hpp>
#include "mrc1_request_queue.h"
#include "poller.h"

namespace mesycontrol
{

Poller::Poller(MRC1RequestQueue &mrc1_queue,
    boost::posix_time::time_duration cycle_interval)
  : m_mrc1_queue(mrc1_queue)
  , m_poll_iter(m_poll_set.end())
  , m_timer(mrc1_queue.get_mrc1_connection()->get_io_service())
  , m_cycle_interval(cycle_interval)
{
  m_mrc1_queue.get_mrc1_connection()->register_status_change_callback(
      boost::bind(&Poller::handle_mrc1_status_change, shared_from_this(), _1, _2, _3, _4));
}

void Poller::set_poll_request(const TCPConnectionPtr &connection, const proto::RequestSetPollItems &items)
{
  std::pair<PollRequestMap::iterator, bool> result(m_poll_requests.insert(
        std::make_pair(connection, proto::RequestSetPollItems())));

  result.first->second.CopyFrom(items);
}

void Poller::remove_poll_request(const TCPConnectionPtr &connection)
{
  m_poll_requests.erase(connection);
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
  m_poll_set.clear();

  for (PollRequestMap::const_iterator it=m_poll_requests.begin();
      it!=m_poll_requests.end(); ++it) {
    const proto::RequestSetPollItems &poll_items(it->second);
    for (int i=0; i<poll_items.items_size(); ++i) {
      const proto::RequestSetPollItems::PollItem &item(poll_items.items(i));
      for (boost::uint32_t par=item.par(); par<item.par()+item.count(); ++par) {
        m_poll_set.insert(boost::make_tuple(item.bus(), item.dev(), par));
      }
    }
  }
}

void Poller::stop_cycle()
{
}

} // namespace mesycontrol
