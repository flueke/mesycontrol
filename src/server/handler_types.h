#ifndef UUID_47558d03_c9a7_4ea8_ad60_1e2e9535f1a5
#define UUID_47558d03_c9a7_4ea8_ad60_1e2e9535f1a5

#include <boost/function.hpp>
#include <mesycontrol/protocol.h>

namespace mesycontrol
{

/** Signature for a response handler. It accepts two Message objects: the first is
 * the original request, the second the response. */
typedef boost::function<void (const MessagePtr &, const MessagePtr &)> ResponseHandler;

/** Signature for a request handler. It accepts the request and a
 * ResponseHandler callback to invoke when the response is ready. */
typedef boost::function<void (const MessagePtr &, ResponseHandler)> RequestHandler;

} // namespace mesycontrol

#endif
