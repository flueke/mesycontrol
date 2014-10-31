#ifndef UUID_04abdb37_fdb6_4230_8bab_1a9552408788
#define UUID_04abdb37_fdb6_4230_8bab_1a9552408788

#include "config.h"
#include <set>
#include <boost/noncopyable.hpp>
#include "tcp_connection.h"
#include "mrc1_request_queue.h"
#include "logging.h"

namespace mesycontrol
{

class TCPConnectionManager: private boost::noncopyable
{
  friend class TCPConnection;

  public:
    TCPConnectionManager(MRC1RequestQueue &mrc1_queue);

    /// Add the specified connection to the manager and start it.
    void start(TCPConnectionPtr c);

    /// Stop the specified connection.
    void stop(TCPConnectionPtr c, bool graceful=true);

    /// Stop all connections.
    void stop_all(bool graceful=true);

    /// Incoming request dispatcher
    void dispatch_request(const TCPConnectionPtr &connection, const MessagePtr &request);

    void send_to_all(const MessagePtr &msg);
    void send_to_all_except(const TCPConnectionPtr &connection, const MessagePtr &msg);

  private:
    void handle_mrc1_response(const TCPConnectionPtr &connection,
        const MessagePtr &request, const MessagePtr &response);

    void handle_read_after_set(
        const MessagePtr &request, const MessagePtr &response);

    void set_write_connection(const TCPConnectionPtr &connection);

    /// The managed connections.
    std::set<TCPConnectionPtr> m_connections;

    /// Handler for MRC commands.
    MRC1RequestQueue& m_mrc1_queue;

    /// The connection currently having write access.
    TCPConnectionPtr m_write_connection;

    /// Local logger instance
    log::Logger m_log;
};

} // namespace mesycontrol

#endif
