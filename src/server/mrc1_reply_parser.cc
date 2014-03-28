#include <boost/regex.hpp>
#include <boost/lexical_cast.hpp>
#include <boost/make_shared.hpp>
#include <iostream>
#include "mrc1_reply_parser.h"

namespace mesycontrol
{

void MRC1ReplyParser::set_current_request(const MessagePtr &request)
{
  m_request  = request;
  m_response = boost::make_shared<Message>();
  m_error_reply_parsed = false;
}

bool MRC1ReplyParser::parse_line(const std::string &reply_line)
{
  if (m_error_reply_parsed) {
    return true; // Ignore the second line of an error reply.
  }

  static const boost::regex re_no_response("^ERR.*NO\\ RESP.*");

  if (regex_match(reply_line, re_no_response)) {
    m_response = Message::make_error_response(error_type::mrc_no_response);
    m_error_reply_parsed = true;
    return false;
  }

  static const boost::regex re_error("^ERR.*");

  if (regex_match(reply_line, re_error)) {
    m_response = Message::make_error_response(error_type::unknown_error);
    m_error_reply_parsed = true;
    return false; // Still need to consume the second line of the error reply.
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
      m_response->type       = message_type::response_bool;
      m_response->bool_value = true;
      return true;

    case message_type::request_scanbus:
      return parse_scanbus(reply_line);

    default:
      m_response = Message::make_error_response(error_type::unknown_error);
      return true;
  }
}

bool MRC1ReplyParser::parse_read_or_set(const std::string &reply_line)
{
  static const boost::regex re_read_or_set("^[SERM]{2}\\ (\\d+)\\ (\\d+)\\ (\\d+)\\ (\\d+)\\s*$");
  boost::smatch matches;

  if (!regex_match(reply_line, matches, re_read_or_set)) {
    m_response = Message::make_error_response(error_type::unknown_error);
    return true;
  }

  m_response = Message::make_read_or_set_response(
      m_request->type,
      boost::lexical_cast<unsigned int>(matches[1]),
      boost::lexical_cast<unsigned int>(matches[2]),
      boost::lexical_cast<unsigned int>(matches[3]),
      boost::lexical_cast<boost::uint16_t>(matches[4]));

  return true;
}

bool MRC1ReplyParser::parse_scanbus(const std::string &reply_line)
{
  static const boost::regex re_header("^ID-SCAN\\ BUS\\ (\\d+):\\s*$");
  static const boost::regex re_body("^(\\d+):\\ (-|((\\d+),\\ (ON|0FF)))\\s*$"); // 0FF with 0 not O!
  boost::smatch matches;

  if (regex_match(reply_line, matches, re_header)) {
    m_response->type = message_type::response_scanbus;
    m_response->bus  = boost::lexical_cast<unsigned int>(matches[1]);
    return false;
  } else if (regex_match(reply_line, matches, re_body)) {
    size_t dev = boost::lexical_cast<size_t>(matches[1]);

    if (matches[4].matched) // device identifier code
      m_response->bus_data[dev].first = boost::lexical_cast<unsigned int>(matches[4]);

    if (matches[5].matched) // ON/OFF status
      m_response->bus_data[dev].second = (matches[5] == "ON");

    if (dev >= 15) {
      return true; // last line of the scanbus output
    }
    return false;
  } else {
      m_response = Message::make_error_response(error_type::unknown_error);
      return true;
  }
  return true;
}

MessagePtr MRC1ReplyParser::get_response_message() const
{
  return m_response;
}

} // namespace mesycontrol
