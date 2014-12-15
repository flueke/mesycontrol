#include <boost/regex.hpp>
#include <boost/lexical_cast.hpp>
#include <boost/make_shared.hpp>
#include <iostream>
#include "mrc1_reply_parser.h"

namespace
{
  static const boost::regex re_no_response("^ERR.*NO\\ RESP.*");
  static const boost::regex re_bus_address("^ERR.*ADDR.*");
  static const boost::regex re_error("^ERR.*");
}

namespace mesycontrol
{
MRC1ReplyParser::MRC1ReplyParser()
  : m_error_lines_to_consume(0)
  , m_scanbus_address_conflict(false)
  , m_log(log::keywords::channel="MRC1ReplyParser")
{
}

void MRC1ReplyParser::set_current_request(const MessagePtr &request)
{
  m_request = request;
  m_response.reset();
  m_error_lines_to_consume = 0;
  m_scanbus_address_conflict = false;
  m_multi_read_lines_left = 0;

  BOOST_LOG_SEV(m_log, log::lvl::trace) << "set_current_request: new request is " << m_request;
}

/** Returns an error response message if the given line matches any of the MRC
 * error messages, otherwise returns a null MessagePtr. */
MessagePtr MRC1ReplyParser::get_error_response(const std::string &reply_line)
{
  if (regex_match(reply_line, re_no_response)) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "MRC: no response";
    return MessageFactory::make_error_response(error_type::mrc_no_response);
  }

  if (regex_match(reply_line, re_bus_address)) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "MRC: address conflict";
    return MessageFactory::make_error_response(error_type::mrc_address_conflict);
  }

  if (regex_match(reply_line, re_error)) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "MRC: error: " << reply_line;
    return MessageFactory::make_error_response(error_type::unknown_error);
  }

  return MessagePtr();
}

bool MRC1ReplyParser::parse_line(const std::string &reply_line)
{
  assert(m_request);

  if (m_error_lines_to_consume) {
    BOOST_LOG_SEV(m_log, log::lvl::trace)
      << "Consuming " << m_error_lines_to_consume << " more lines of input";
    return --m_error_lines_to_consume == 0;
  }

  switch (m_request->type) {
    case message_type::request_set:
    case message_type::request_mirror_set:
    case message_type::request_read:
    case message_type::request_mirror_read:
      return parse_read_or_set(reply_line);

    case message_type::request_rc_on:
    case message_type::request_rc_off:
    case message_type::request_reset:
    case message_type::request_copy:
      return parse_other(reply_line);

    case message_type::request_scanbus:
      return parse_scanbus(reply_line);

    case message_type::request_read_multi:
      assert(m_request->len);
      return parse_read_multi(reply_line);

    default:
      BOOST_LOG_SEV(m_log, log::lvl::error)
        << "message type " << m_request->type << " not handled by reply parser!";
      m_response = MessageFactory::make_error_response(error_type::unknown_error);
      return true;
  }
  return true;
}

bool MRC1ReplyParser::parse_read_or_set(const std::string &reply_line)
{
  static const boost::regex re_read_or_set("^[SERM]{2}\\ (\\d+)\\ (\\d+)\\ (\\d+)\\ (-?\\d+)\\s*$");
  boost::smatch matches;

  m_response = get_error_response(reply_line);
  if (m_response) {
    return true;
  }

  if (!regex_match(reply_line, matches, re_read_or_set)) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "error parsing " << reply_line;
    m_response = MessageFactory::make_error_response(error_type::mrc_parse_error);
    return true;
  }

  m_response = MessageFactory::make_read_or_set_response(
      m_request->type,
      boost::lexical_cast<unsigned int>(matches[1]),
      boost::lexical_cast<unsigned int>(matches[2]),
      boost::lexical_cast<unsigned int>(matches[3]),
      boost::lexical_cast<boost::int32_t>(matches[4]));

  return true;
}

bool MRC1ReplyParser::parse_scanbus(const std::string &reply_line)
{
  static const boost::regex re_header("^ID-SCAN\\ BUS\\ (\\d+):\\s*$");
  static const boost::regex re_body("^(\\d+):\\ (-|((\\d+),\\ (ON|0FF)))\\s*$"); // 0FF with 0 not O!
  static const boost::regex re_no_resp("^ERR:NO RESP\\s*$");
  boost::smatch matches;

  if (regex_match(reply_line, matches, re_header)) {
    Message::ScanbusData scanbus_data;

    std::fill(scanbus_data.begin(), scanbus_data.end(),
        std::make_pair(static_cast<uint8_t>(0u), rc_status::off));

    m_response = MessageFactory::make_scanbus_response(
        boost::lexical_cast<unsigned int>(matches[1]),
        scanbus_data);

    return false;
  } else if (regex_match(reply_line, matches, re_bus_address)) {
    /* ERR:ADDR is reported on the line before the actual address info line.
     * m_scanbus_address_conflict records if an address conflict was
     * reported. */
    m_scanbus_address_conflict = true;
    return false;
  } else if (regex_match(reply_line, matches, re_body)) {

    size_t dev = boost::lexical_cast<size_t>(matches[1]);

    if (m_response && m_response->type == message_type::response_scanbus) {

      if (matches[4].matched) // device identifier code
        m_response->bus_data[dev].first = boost::lexical_cast<unsigned int>(matches[4]);

      if (matches[5].matched) // ON/OFF status
        m_response->bus_data[dev].second = (matches[5] == "ON" ? rc_status::on : rc_status::off);

      if (m_scanbus_address_conflict) {
        BOOST_LOG_SEV(m_log, log::lvl::debug)
          << "Scanbus: bus=" << static_cast<boost::uint16_t>(m_response->bus)
          << ", dev=" << dev << ": address conflict";
        m_response->bus_data[dev].second = rc_status::address_conflict;
        m_scanbus_address_conflict = false;
      }
    } else {
      BOOST_LOG_SEV(m_log, log::lvl::error)
        << "Scanbus: received body line without prior header line";
      m_response = MessageFactory::make_error_response(error_type::mrc_parse_error);
      /* Consume the rest of the scanbus data. */
      m_error_lines_to_consume = 15 - dev;
    }

    return (dev >= 15); // 15 is the last bus address
  } else if (regex_match(reply_line, matches, re_no_resp)) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "Error parsing scanbus reply: no response";
    m_response = MessageFactory::make_error_response(error_type::mrc_no_response);
    return true;
  }

  BOOST_LOG_SEV(m_log, log::lvl::error) << "Error parsing scanbus reply. Received '" << reply_line << "'";
  m_response = MessageFactory::make_error_response(error_type::mrc_parse_error);
  return true;
}

bool MRC1ReplyParser::parse_other(const std::string &reply_line)
{
  m_response = get_error_response(reply_line);

  if (m_response) {
    m_error_lines_to_consume = 1;
    return false;
  }

  m_response = MessageFactory::make_bool_response(true);
  return true;
}

bool MRC1ReplyParser::parse_read_multi(const std::string &reply_line)
{
  static const boost::regex re_number("^(-?\\d+)$");

  assert(m_request);

  // error check for each line
  MessagePtr error_response(get_error_response(reply_line));
  if (error_response) {
    m_response = error_response;
    return true;
  }

  // init
  if (m_multi_read_lines_left == 0) {
    BOOST_LOG_SEV(m_log, log::lvl::trace) << "parse_read_multi: request length = "
      << static_cast<boost::int32_t>(m_request->len);

    m_multi_read_lines_left = m_request->len;
    m_response = MessageFactory::make_read_multi_response(
        m_request->bus, m_request->dev, m_request->par);

  } else {
    BOOST_LOG_SEV(m_log, log::lvl::trace) << "parse_read_multi: "
      << m_multi_read_lines_left << " lines left to read";
  }

  boost::smatch matches;

  if (!regex_match(reply_line, matches, re_number)) {
    BOOST_LOG_SEV(m_log, log::lvl::error)
      << "error parsing read_multi response: non-numeric response line: " << reply_line;
    m_response = MessageFactory::make_error_response(error_type::mrc_parse_error);
    m_error_lines_to_consume = m_multi_read_lines_left - 1;
    return false;
  }

  boost::int32_t value(boost::lexical_cast<boost::int32_t>(matches[1]));
  BOOST_LOG_SEV(m_log, log::lvl::trace) << "parse_read_multi: got value " << value;
  m_response->values.push_back(value);
  return --m_multi_read_lines_left == 0;
}

MessagePtr MRC1ReplyParser::get_response_message() const
{
  return m_response;
}

} // namespace mesycontrol
