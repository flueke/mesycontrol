#ifndef UUID_5503bd19_8e1b_48bf_822e_c613b018d900
#define UUID_5503bd19_8e1b_48bf_822e_c613b018d900

#include "config.h"
#include "protocol.h"
#include "logging.h"

namespace mesycontrol
{

class MRC1ReplyParser
{
  public:
    MRC1ReplyParser();
    void set_current_request(const MessagePtr &request);

    /* Parses the given line.
     * Returns true if parsing is complete, false if more input is needed. */
    bool parse_line(const std::string &reply_line);

    MessagePtr get_response_message() const;

  private:
    MessagePtr get_error_response(const std::string &reply_line); 
    bool parse_read_or_set(const std::string &reply_line);
    bool parse_scanbus(const std::string &reply_line);
    bool parse_other(const std::string &reply_line);
    bool parse_read_multi(const std::string &reply_line);

    MessagePtr m_request;
    MessagePtr m_response;

    size_t m_error_lines_to_consume;
    bool m_scanbus_address_conflict;
    size_t m_multi_read_lines_left;

    log::Logger m_log;
};

} // namespace mesycontrol

#endif
