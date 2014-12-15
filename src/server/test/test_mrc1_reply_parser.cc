#define BOOST_TEST_MODULE MRC1ReplyParser
#include <boost/test/unit_test.hpp>

#include <boost/assign.hpp>
#include <boost/make_shared.hpp>
#include <boost/lexical_cast.hpp>

#include <mrc1_reply_parser.h>

BOOST_AUTO_TEST_CASE(parse_read_multi)
{
  using namespace mesycontrol;

  MessagePtr request(boost::make_shared<Message>());
  request->type = message_type::request_read_multi;
  request->bus  = 0;
  request->dev  = 0;
  request->par  = 0;
  request->len  = 3;

  std::vector<const char *> data = boost::assign::list_of("42")("43")("44");

  mesycontrol::MRC1ReplyParser parser;
  parser.set_current_request(request);

  for (size_t i=0; i<data.size(); ++i) {
    bool result = parser.parse_line(data[i]);
    if (i < data.size()-1) {
      BOOST_REQUIRE(!result);
    } else {
      BOOST_REQUIRE(result);
    }
  }

  MessagePtr response(parser.get_response_message());
  BOOST_REQUIRE(response->type == message_type::response_read_multi);
  BOOST_REQUIRE(response->values.size() == 3);

  for (size_t i=0; i<data.size(); ++i) {
    boost::int32_t intval(boost::lexical_cast<boost::int32_t>(data[i]));
    BOOST_REQUIRE(intval == response->values[i]);
  }
}
