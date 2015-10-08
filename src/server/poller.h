#ifndef UUID_4dece6c3_f25f_43a6_aea1_0d9058e43cce
#define UUID_4dece6c3_f25f_43a6_aea1_0d9058e43cce

#include <boost/cstdint.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/noncopyable.hpp>
#include <boost/unordered_set.hpp>
#include <map>
#include <ostream>
#include <vector>

#include "logging.h"
#include "protocol.h"
#include "tcp_connection.h"

namespace mesycontrol
{

class MRC1RequestQueue;

struct PollItem
{
  boost::uint32_t bus;
  boost::uint32_t dev;
  boost::uint32_t par;

  PollItem(boost::uint32_t bus, boost::uint32_t dev, boost::uint32_t par)
    : bus(bus)
    , dev(dev)
    , par(par)
  {}

  inline bool operator==(const PollItem &o) const
  {
    return bus == o.bus && dev == o.dev && par == o.par;
  }
};

// needed by boost::unordered_set
std::size_t hash_value(const PollItem &item);

typedef std::vector<PollItem> PollItems;

std::ostream &operator<<(std::ostream &os, const PollItems &items);

struct PollResult: public PollItem
{
  boost::uint32_t val;

  PollResult(boost::uint32_t bus, boost::uint32_t dev, boost::uint32_t par,
      boost::uint32_t val)
    : PollItem(bus, dev, par)
    , val(val)
  {}
};

std::size_t hash_value(const PollResult &result);
std::ostream &operator<<(std::ostream &os, const PollResult &result);

class Poller
  : public boost::enable_shared_from_this<Poller>
  , private boost::noncopyable
{
  public:
    /// Collects result items to be sent to clients.
    typedef boost::unordered_set<PollResult> ResultType;

    /// signature for result callbacks
    typedef boost::function<void (const ResultType &)> ResultHandler;

    explicit Poller(MRC1RequestQueue &mrc1_queue,
        boost::posix_time::time_duration min_interval = boost::posix_time::milliseconds(5));

    void set_poll_items(const TCPConnectionPtr &connection, const PollItems &items);
    void remove_poller(const TCPConnectionPtr &connection);

    void register_result_handler(const ResultHandler &handler)
    { m_result_handlers.push_back(handler); }

    void start();
    void stop();

    /// Notify the poller that a parameters value has been changed (due to a
    /// set request). If this pollers result contains the given parameter its
    /// value will be updated.
    void notify_parameter_changed(
        boost::uint32_t bus,
        boost::uint32_t dev,
        boost::uint32_t par,
        boost::uint32_t val);

  private:
    /// Maps connections to poll requests
    typedef std::map<TCPConnectionPtr, PollItems> PollItemsMap;

    /// Set of items to poll. These items are created by expanding all
    /// PollItem instances in PollItemsMap.
    typedef boost::unordered_set<PollItem> PollSet;

    void start_cycle();
    void stop_cycle();
    void poll_next();

    void handle_response(const MessagePtr &request, const MessagePtr &response);
    void notify_cycle_complete();
    void handle_timeout(const boost::system::error_code &ec);

    log::Logger m_log;
    MRC1RequestQueue& m_queue;
    PollItemsMap m_map;
    PollSet m_set;
    PollSet::const_iterator m_set_iter;
    boost::asio::deadline_timer m_timer;
    boost::posix_time::time_duration m_min_interval;
    ResultType m_result;
    std::vector<ResultHandler> m_result_handlers;
    bool m_stopped;
};

class ScanbusPoller
  : public boost::enable_shared_from_this<ScanbusPoller>
  , private boost::noncopyable
{
  public:
    typedef boost::function<void (const MessagePtr &)> ResultHandler;

    explicit ScanbusPoller(MRC1RequestQueue &mrc1_queue,
        boost::posix_time::time_duration min_interval = boost::posix_time::milliseconds(2000));

    void register_result_handler(const ResultHandler &handler)
    { m_result_handlers.push_back(handler); }

    void start();
    void stop();

  private:
    void handle_response(const MessagePtr &request, const MessagePtr &response);
    void handle_timeout(const boost::system::error_code &ec);

    log::Logger m_log;
    MRC1RequestQueue& m_queue;
    boost::asio::deadline_timer m_timer;
    boost::posix_time::time_duration m_min_interval;
    std::vector<ResultHandler> m_result_handlers;
    bool m_stopped;
};

} // namespace mesycontrol

#endif
