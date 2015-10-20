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
  , m_multi_read_lines_left(0)
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
  proto::ResponseError::ErrorType error_type =
    static_cast<proto::ResponseError::ErrorType>(-1);

  if (regex_match(reply_line, re_no_response)) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "MRC: no response";
    error_type = proto::ResponseError::NO_RESPONSE;
  }

  else if (regex_match(reply_line, re_bus_address)) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "MRC: address conflict";
    error_type = proto::ResponseError::ADDRESS_CONFLICT;
  }

  else if (regex_match(reply_line, re_error)) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "MRC: error: " << reply_line;
    error_type = proto::ResponseError::UNKNOWN;
  }

  if (error_type >= 0)
    return MessageFactory::make_error_response(error_type);

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

  switch (m_request->type()) {
    case proto::Message::REQ_SET:
    case proto::Message::REQ_READ:
      return parse_read_or_set(reply_line);

    case proto::Message::REQ_RC:
    case proto::Message::REQ_RESET:
    case proto::Message::REQ_COPY:
      return parse_other(reply_line);

    case proto::Message::REQ_SCANBUS:
      return parse_scanbus(reply_line);

    default:
      BOOST_LOG_SEV(m_log, log::lvl::error)
        << "message type "
        << proto::Message::Type_Name(m_request->type())
        << " not handled by reply parser!";
      m_response = MessageFactory::make_error_response(proto::ResponseError::UNKNOWN);
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
    m_error_lines_to_consume = 1;
    return false;
  }

  if (!regex_match(reply_line, matches, re_read_or_set)) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "error parsing " << reply_line;
    m_response = MessageFactory::make_error_response(proto::ResponseError::PARSE_ERROR);
    return true;
  }

  boost::uint8_t bus = boost::lexical_cast<unsigned int>(matches[1]);
  boost::uint8_t dev = boost::lexical_cast<unsigned int>(matches[2]);
  boost::uint8_t par = boost::lexical_cast<unsigned int>(matches[3]);
  boost::int32_t val = boost::lexical_cast<boost::int32_t>(matches[4]);

  if (m_request->type() == proto::Message::REQ_READ) {
    m_response = MessageFactory::make_read_response(bus, dev, par, val,
        m_request->request_read().mirror());
  } else if (m_request->type() == proto::Message::REQ_SET) {
    m_response = MessageFactory::make_set_response(bus, dev, par, val,
        m_request->request_read().mirror());
  } else {
    return false;
  }

  return true;
}

bool MRC1ReplyParser::parse_scanbus(const std::string &reply_line)
{
  static const boost::regex re_header("^ID-SCAN\\ BUS\\ (\\d+):\\s*$");
  static const boost::regex re_body("^(\\d+):\\ (-|((\\d+),\\ (ON|0FF)))\\s*$"); // 0FF with 0 not O!
  static const boost::regex re_no_resp("^ERR:NO RESP\\s*$");
  boost::smatch matches;

  if (regex_match(reply_line, matches, re_header)) {
    m_response = MessageFactory::make_scanbus_response(
        boost::lexical_cast<unsigned int>(matches[1]));

    return false;
  } else if (regex_match(reply_line, matches, re_bus_address)) {
    /* ERR:ADDR is reported on the line before the actual address info line.
     * m_scanbus_address_conflict records if an address conflict was
     * reported. */
    m_scanbus_address_conflict = true;
    return false;
  } else if (regex_match(reply_line, matches, re_body)) {

    size_t dev = boost::lexical_cast<size_t>(matches[1]);

    if (m_response && m_response->type() == proto::Message::RESP_SCANBUS) {
      proto::ScanbusResult::ScanbusEntry *entry(m_response->mutable_scanbus_result()
          ->add_entries());

      if (matches[4].matched) // device identifier code
        entry->set_idc(boost::lexical_cast<unsigned int>(matches[4]));

      if (matches[5].matched) // ON/OFF status
        entry->set_rc(matches[5] == "ON");

      entry->set_conflict(m_scanbus_address_conflict);
      m_scanbus_address_conflict = false;
    } else {
      BOOST_LOG_SEV(m_log, log::lvl::error)
        << "Scanbus: received body line without prior header line";
      m_response = MessageFactory::make_error_response(proto::ResponseError::PARSE_ERROR);
      /* Consume the rest of the scanbus data. */
      m_error_lines_to_consume = 15 - dev;
    }

    return (dev >= 15); // 15 is the last bus address
  } else if (regex_match(reply_line, matches, re_no_resp)) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "Error parsing scanbus reply: no response";
    m_response = MessageFactory::make_error_response(proto::ResponseError::NO_RESPONSE);
    return true;
  }

  BOOST_LOG_SEV(m_log, log::lvl::error)
    << "Error parsing scanbus reply. Received '" << reply_line << "'";

  m_response = MessageFactory::make_error_response(proto::ResponseError::PARSE_ERROR);
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
      << static_cast<boost::int32_t>(m_request->request_read_multi().count());

    m_multi_read_lines_left = m_request->request_read_multi().count();
    m_response = MessageFactory::make_read_multi_response(
        m_request->request_read_multi().bus(),
        m_request->request_read_multi().dev(),
        m_request->request_read_multi().par());

  } else {
    BOOST_LOG_SEV(m_log, log::lvl::trace) << "parse_read_multi: "
      << m_multi_read_lines_left << " lines left to read";
  }

  boost::smatch matches;

  if (!regex_match(reply_line, matches, re_number)) {
    BOOST_LOG_SEV(m_log, log::lvl::error)
      << "error parsing read_multi response: non-numeric response line: " << reply_line;
    m_response = MessageFactory::make_error_response(proto::ResponseError::PARSE_ERROR);
    m_error_lines_to_consume = m_multi_read_lines_left - 1;
    return false;
  }

  boost::int32_t value;
  std::stringstream ss;
  ss << std::hex << matches[1];
  ss >> value;

  BOOST_LOG_SEV(m_log, log::lvl::trace) << "parse_read_multi: got value " << value;
  m_response->mutable_response_read_multi()->add_values(value);
  return --m_multi_read_lines_left == 0;
}

MessagePtr MRC1ReplyParser::get_response_message() const
{
  return m_response;
}

} // namespace mesycontrol
