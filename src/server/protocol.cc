#include <boost/assign.hpp>
#include <boost/foreach.hpp>
#include <boost/format.hpp>
#include <boost/make_shared.hpp>
#include <map>
#ifndef __MINGW32__
#include <arpa/inet.h>
#else
#include <Winsock2.h>
#endif
#include <stdexcept>
#include "protocol.h"

namespace mesycontrol
{

namespace
{
  MessagePtr make_message(const proto::Message::Type &type)
  {
    MessagePtr ret(boost::make_shared<proto::Message>());
    ret->set_type(type);
    return ret;
  }

  MessagePtr make_status_message(
      const proto::Message::Type &type,
      const proto::MRCStatus::StatusCode &status,
      const boost::system::error_code &reason,
      const std::string &version,
      bool has_read_multi)
  {
    MessagePtr ret(make_message(type));
    ret->mutable_mrc_status()->set_code(status);
    ret->mutable_mrc_status()->set_reason(reason.value());
    if (reason.value())
      ret->mutable_mrc_status()->set_info(reason.message());
    ret->mutable_mrc_status()->set_version(version);
    ret->mutable_mrc_status()->set_has_read_multi(has_read_multi);
    return ret;
  }
}

MessagePtr MessageFactory::make_scanbus_response(boost::uint8_t bus)
{
  MessagePtr ret(make_message(proto::Message::RESP_SCANBUS));
  ret->mutable_scanbus_result()->set_bus(bus);
  return ret;
}

MessagePtr MessageFactory::make_scanbus_request(boost::uint8_t bus)
{
  MessagePtr ret(make_message(proto::Message::REQ_SCANBUS));
  ret->mutable_request_scanbus()->set_bus(bus);
  return ret;
}

MessagePtr MessageFactory::make_read_request(boost::uint8_t bus, boost::uint8_t dev,
    boost::uint8_t par, bool mirror)
{
  MessagePtr ret(make_message(proto::Message::REQ_READ));
  ret->mutable_request_read()->set_bus(bus);
  ret->mutable_request_read()->set_dev(dev);
  ret->mutable_request_read()->set_par(par);
  ret->mutable_request_read()->set_mirror(mirror);
  return ret;
}

MessagePtr MessageFactory::make_read_response(boost::uint8_t bus, boost::uint8_t dev,
    boost::uint8_t par, boost::int32_t val, bool mirror)
{
  MessagePtr ret(make_message(proto::Message::RESP_READ));
  ret->mutable_response_read()->set_bus(bus);
  ret->mutable_response_read()->set_dev(dev);
  ret->mutable_response_read()->set_par(par);
  ret->mutable_response_read()->set_val(val);
  ret->mutable_response_read()->set_mirror(mirror);
  return ret;
}

MessagePtr MessageFactory::make_set_response(boost::uint8_t bus, boost::uint8_t dev,
    boost::uint8_t par, boost::int32_t val, boost::int32_t requested_value, bool mirror)
{
  MessagePtr ret(make_message(proto::Message::RESP_SET));
  ret->mutable_set_result()->set_bus(bus);
  ret->mutable_set_result()->set_dev(dev);
  ret->mutable_set_result()->set_par(par);
  ret->mutable_set_result()->set_val(val);
  ret->mutable_set_result()->set_requested_value(requested_value);
  ret->mutable_set_result()->set_mirror(mirror);
  return ret;
}

MessagePtr MessageFactory::make_bool_response(bool bool_value)
{
  MessagePtr ret(make_message(proto::Message::RESP_BOOL));
  ret->mutable_response_bool()->set_value(bool_value);
  return ret;
}

MessagePtr MessageFactory::make_error_response(const proto::ResponseError::ErrorType &error)
{
  MessagePtr ret(make_message(proto::Message::RESP_ERROR));
  ret->mutable_response_error()->set_type(error);
  return ret;
}

MessagePtr MessageFactory::make_write_access_notification(bool has_write_access, bool can_acquire)
{
  MessagePtr ret(make_message(proto::Message::NOTIFY_WRITE_ACCESS));
  ret->mutable_notify_write_access()->set_has_access(has_write_access);
  ret->mutable_notify_write_access()->set_can_acquire(can_acquire);
  return ret;
}

MessagePtr MessageFactory::make_silent_mode_notification(bool silence_active)
{
  MessagePtr ret(make_message(proto::Message::NOTIFY_SILENCED));
  ret->mutable_notify_silenced()->set_silenced(silence_active);
  return ret;
}

MessagePtr MessageFactory::make_parameter_set_notification(boost::uint8_t bus, boost::uint8_t dev,
    boost::uint8_t par, boost::int32_t val, boost::int32_t requested_value, bool mirror)
{
  MessagePtr ret(make_message(proto::Message::NOTIFY_SET));
  ret->mutable_set_result()->set_bus(bus);
  ret->mutable_set_result()->set_dev(dev);
  ret->mutable_set_result()->set_par(par);
  ret->mutable_set_result()->set_val(val);
  ret->mutable_set_result()->set_requested_value(requested_value);
  ret->mutable_set_result()->set_mirror(mirror);
  return ret;
}

MessagePtr MessageFactory::make_mrc_status_response(
    const proto::MRCStatus::StatusCode &status,
    const boost::system::error_code &reason,
    const std::string &version,
    bool has_read_multi)
{
  return make_status_message(proto::Message::RESP_MRC_STATUS,
      status, reason, version, has_read_multi);
}

MessagePtr MessageFactory::make_mrc_status_notification(
    const proto::MRCStatus::StatusCode &status,
    const boost::system::error_code &reason,
    const std::string &version,
    bool has_read_multi)
{
  return make_status_message(proto::Message::NOTIFY_MRC_STATUS,
      status, reason, version, has_read_multi);
}

MessagePtr MessageFactory::make_read_multi_response(boost::uint8_t bus, boost::uint8_t dev,
    boost::uint8_t start_param, const std::vector<boost::int32_t> &values)
{
  MessagePtr ret(make_message(proto::Message::RESP_READ_MULTI));
  ret->mutable_response_read_multi()->set_bus(bus);
  ret->mutable_response_read_multi()->set_dev(dev);
  ret->mutable_response_read_multi()->set_par(start_param);

  for (std::vector<boost::int32_t>::const_iterator it=values.begin();
      it != values.end(); ++it) {
    ret->mutable_response_read_multi()->add_values(*it);
  }

  return ret;
}

bool is_mrc1_command(const MessagePtr &msg)
{
  switch (msg->type()) {
    case proto::Message::REQ_SCANBUS:
    case proto::Message::REQ_READ:
    case proto::Message::REQ_SET:
    case proto::Message::REQ_RC:
    case proto::Message::REQ_RESET:
    case proto::Message::REQ_COPY:
    case proto::Message::REQ_READ_MULTI:
      return true;
    default:
      return false;
  }
}

bool is_mrc1_write_command(const MessagePtr &msg)
{
  switch (msg->type()) {
    case proto::Message::REQ_SET:
    case proto::Message::REQ_RC:
    case proto::Message::REQ_RESET:
    case proto::Message::REQ_COPY:
      return true;
    default:
      return false;
  }
}

std::string get_mrc1_command_string(const MessagePtr &msg)
{
  switch (msg->type()) {
    case proto::Message::REQ_SCANBUS:
      return boost::str(boost::format("SC %1%")
          % msg->request_scanbus().bus());

    case proto::Message::REQ_RC:
      return boost::str(boost::format("%1% %2% %3%")
          % (msg->request_rc().rc() ? "ON" : "OFF")
          % msg->request_rc().bus()
          % msg->request_rc().dev());

    case proto::Message::REQ_RESET:
      return boost::str(boost::format("RST %1% %2%")
          % msg->request_reset().bus()
          % msg->request_reset().dev());

    case proto::Message::REQ_COPY:
      return boost::str(boost::format("CP %1% %2%")
          % msg->request_copy().bus()
          % msg->request_copy().dev());

    case proto::Message::REQ_READ:
      return boost::str(boost::format("%1% %2% %3% %4%")
          % (msg->request_read().mirror() ? "RM" : "RE")
          % msg->request_read().bus()
          % msg->request_read().dev()
          % msg->request_read().par());

    case proto::Message::REQ_SET:
      return boost::str(boost::format("%1% %2% %3% %4% %5%")
          % (msg->request_set().mirror() ? "SM" : "SE")
          % msg->request_set().bus()
          % msg->request_set().dev()
          % msg->request_set().par()
          % msg->request_set().val());

    case proto::Message::REQ_READ_MULTI:
      return boost::str(boost::format("RB %1% %2% %3% %4%")
          % msg->request_read_multi().bus()
          % msg->request_read_multi().dev()
          % msg->request_read_multi().par()
          % msg->request_read_multi().count());

    default:
      BOOST_THROW_EXCEPTION(std::runtime_error("not a mrc command request"));
  }
}

std::string get_message_info(const MessagePtr &msg)
{
  if (msg->type() == proto::Message::RESP_MRC_STATUS
      || msg->type() == proto::Message::NOTIFY_MRC_STATUS) {

    return boost::str(
        boost::format("%1%: status=%2%, version=%3%, info=\"%4%\", rb_supported=%5%")
        % proto::Message::Type_Name(msg->type())
        % proto::MRCStatus::StatusCode_Name(msg->mrc_status().code())
        % msg->mrc_status().version()
        % msg->mrc_status().info()
        % msg->mrc_status().has_read_multi());
  }

  if (msg->type() == proto::Message::RESP_ERROR) {
    return boost::str(
        boost::format("%1%: %2%, info=\"%3%\"")
        % proto::Message::Type_Name(msg->type())
        % proto::ResponseError::ErrorType_Name(msg->response_error().type())
        % msg->response_error().info());
  }

  if (is_mrc1_command(msg)) {
    return boost::str(
        boost::format("%1%: \"%2%\"")
        % proto::Message::Type_Name(msg->type())
        % get_mrc1_command_string(msg));
  }

  return proto::Message::Type_Name(msg->type());
}

} // namespace mesycontrol
