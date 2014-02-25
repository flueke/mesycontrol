#ifndef UUID_5503bd19_8e1b_48bf_822e_c613b018d900
#define UUID_5503bd19_8e1b_48bf_822e_c613b018d900

#include "config.h"
#include <mesycontrol/protocol.h>

namespace mesycontrol
{

class MRC1ReplyParser
{
  public:
    void set_current_request(const MessagePtr &request);

    /* Parses the given line.
     * Returns true if parsing is complete, false if more input is needed. */
    bool parse_line(const std::string &reply_line);

    MessagePtr get_response_message() const;

  private:
    bool parse_read_or_set(const std::string &reply_line);
    bool parse_scanbus(const std::string &reply_line);

    MessagePtr m_request;
    MessagePtr m_response;

    bool m_error_reply_parsed;
};

} // namespace mesycontrol

#endif
