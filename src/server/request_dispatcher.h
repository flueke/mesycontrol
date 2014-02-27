#ifndef UUID_bfe8efa7_a34a_42dc_b95f_3780fdb010c5
#define UUID_bfe8efa7_a34a_42dc_b95f_3780fdb010c5

#include "config.h"
#include <queue>
#include <utility>
#include "mrc1_connection.h"

namespace mesycontrol
{

class RequestDispatcher
{
  public:
    RequestDispatcher(const boost::shared_ptr<MRC1Connection> &mrc1_connection);
    void dispatch(const MessagePtr &request, ResponseHandler response_handler);

  private:
    typedef std::deque<std::pair<MessagePtr, ResponseHandler> > MRC1RequestQueue;

    void handle_mrc1_response(const MessagePtr &request, const MessagePtr &response);
    void try_send_mrc1_request();
    void dispatch_control_message(const MessagePtr &request, ResponseHandler response_handler);

    boost::shared_ptr<MRC1Connection> m_mrc1_connection;
    MRC1RequestQueue m_mrc1_request_queue;
};

} // namespace mesycontrol

#endif
