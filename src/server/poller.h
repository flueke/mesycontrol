#ifndef UUID_4dece6c3_f25f_43a6_aea1_0d9058e43cce
#define UUID_4dece6c3_f25f_43a6_aea1_0d9058e43cce

#include <boost/cstdint.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/noncopyable.hpp>
#include <boost/tuple/tuple_comparison.hpp>
#include <boost/unordered_set.hpp>
#include <map>
#include <vector>

#include "logging.h"
#include "protocol.h"
#include "tcp_connection.h"

namespace mesycontrol
{

class MRC1RequestQueue;

class Poller
  : public boost::enable_shared_from_this<Poller>
  , private boost::noncopyable
{
  public:
    explicit Poller(MRC1RequestQueue &mrc1_queue,
        boost::posix_time::time_duration cycle_interval = boost::posix_time::milliseconds(250));

    void set_poll_request(const TCPConnectionPtr &connection,
        const proto::RequestSetPollItems &items);

    void remove_poll_request(const TCPConnectionPtr &connection);

  private:
    /// Maps connections to poll requests
    typedef std::map<TCPConnectionPtr, proto::RequestSetPollItems> PollRequestMap;

    /// Tuple contents: bus, dev, par
    typedef boost::tuple<boost::uint32_t, boost::uint32_t, boost::uint32_t> PollItem;

    /// Set of items to poll. These items a created by expanding all
    /// RequestSetPollItems::PollItem instances in PollRequestMap.
    typedef boost::unordered_set<PollItem> PollSet;

    void handle_mrc1_status_change(const proto::MRCStatus::Status &status,
        const std::string &info, const std::string &version, bool has_read_multi);
    void start_cycle();
    void stop_cycle();

    MRC1RequestQueue& m_mrc1_queue;
    PollRequestMap m_poll_requests;
    PollSet m_poll_set;
    PollSet::const_iterator m_poll_iter;
    log::Logger m_log;
    boost::asio::deadline_timer m_timer;
    boost::posix_time::time_duration m_cycle_interval;
};


} // namespace mesycontrol

namespace boost
{
  inline size_t hash_value(const boost::tuple<boost::uint32_t, boost::uint32_t, boost::uint32_t> &t)
  {
    return t.get<0>() + t.get<1>() * 10 + t.get<2>() * 100;
  }
}

namespace mesycontrol
{
  inline size_t hash_value(const boost::tuple<boost::uint32_t, boost::uint32_t, boost::uint32_t> &t)
  {
    return t.get<0>() + t.get<1>() * 10 + t.get<2>() * 100;
  }
}

#endif
