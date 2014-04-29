#ifndef UUID_9fca8a51_4f4a_4dc7_904d_a9286b06b62d
#define UUID_9fca8a51_4f4a_4dc7_904d_a9286b06b62d

#include <boost/asio/steady_timer.hpp>
#include "mrc1_connection.h"
#include "logging.h"

namespace mesycontrol
{

class MRC1RequestQueue: private boost::noncopyable
{
  public:
    MRC1RequestQueue(const boost::shared_ptr<MRC1Connection> &mrc1_connection);

    void queue_request(const MessagePtr &request, ResponseHandler response_handler);

    boost::asio::steady_timer::duration get_retry_timeout() const
    { return m_retry_timeout; }

    void set_retry_timeout(const boost::asio::steady_timer::duration &timeout)
    { m_retry_timeout = timeout; }

    boost::shared_ptr<MRC1Connection> get_mrc1_connection() const
    { return m_mrc1_connection; }

    static const boost::asio::steady_timer::duration default_retry_timeout;

  private:
    typedef std::deque<std::pair<MessagePtr, ResponseHandler> > QueueType;

    void handle_mrc1_response(const MessagePtr &request, const MessagePtr &response);
    void try_send_mrc1_request();
    void handle_retry_timer(const boost::system::error_code &);

    boost::shared_ptr<MRC1Connection> m_mrc1_connection;
    QueueType m_request_queue;
    boost::asio::steady_timer::duration m_retry_timeout;
    boost::asio::steady_timer m_retry_timer;
    log::Logger m_log;
};

}

#endif
