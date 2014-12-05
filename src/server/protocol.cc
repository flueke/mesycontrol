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

struct MessageInfo
{
  MessageInfo(size_t sz, const char *type_str)
    : size(sz)
    , type_string(type_str)
  {}

  ssize_t size;             // the message payload size in bytes. -1 for variable message size
  const char *type_string;  // message type as a string
};

typedef std::map<message_type::MessageType, MessageInfo> MessageInfoMap;

const MessageInfoMap &get_message_info_map()
{
  static MessageInfoMap data = boost::assign::map_list_of
    (message_type::request_scanbus,                 MessageInfo(1, "request_scanbus"))      // bus
    (message_type::request_rc_on,                   MessageInfo(2, "request_rc_on"))        // bus dev
    (message_type::request_rc_off,                  MessageInfo(2, "request_rc_off"))       // bus dev
    (message_type::request_reset,                   MessageInfo(2, "request_reset"))        // bus dev
    (message_type::request_copy,                    MessageInfo(2, "request_copy"))         // bus dev
    (message_type::request_read,                    MessageInfo(3, "request_read"))         // bus dev par
    (message_type::request_mirror_read,             MessageInfo(3, "request_mirror_read"))  // bus dev par
    (message_type::request_set,                     MessageInfo(7, "request_set"))          // bus dev par val
    (message_type::request_mirror_set,              MessageInfo(7, "request_mirror_set"))   // bus dev par val
    (message_type::request_read_multi,              MessageInfo(4, "request_read_multi"))   // bus dev par len

    (message_type::request_has_write_access,        MessageInfo(0, "request_has_write_access"))
    (message_type::request_acquire_write_access,    MessageInfo(1, "request_acquire_write_access")) // bool
    (message_type::request_release_write_access,    MessageInfo(0, "request_release_write_access"))
    (message_type::request_in_silent_mode,          MessageInfo(0, "request_in_silent_mode"))
    (message_type::request_set_silent_mode,         MessageInfo(1, "request_set_silent_mode")) // bool
    (message_type::request_force_write_access,      MessageInfo(0, "request_force_write_access"))
    (message_type::request_mrc_status,              MessageInfo(0, "request_mrc_status"))

    (message_type::response_scanbus,                MessageInfo(33, "response_scanbus"))     // bus (idc,bool){16}
    (message_type::response_read,                   MessageInfo( 7, "response_read"))        // bus dev par val
    (message_type::response_set,                    MessageInfo( 7, "response_set"))         // bus dev par val
    (message_type::response_mirror_read,            MessageInfo( 7, "response_mirror_read")) // bus dev par val
    (message_type::response_mirror_set,             MessageInfo( 7, "response_mirror_set"))  // bus dev par val
    (message_type::response_read_multi,             MessageInfo(-1, "response_read_multi"))  // bus dev par values

    (message_type::response_bool,                   MessageInfo(1, "response_bool"))        // bool value
    (message_type::response_error,                  MessageInfo(1, "response_error"))       // error value
    (message_type::response_mrc_status,             MessageInfo(1, "response_mrc_status"))

    (message_type::notify_write_access,             MessageInfo(1, "notify_write_access"))              // bool
    (message_type::notify_silent_mode,              MessageInfo(1, "notify_silent_mode"))               // bool
    (message_type::notify_set,                      MessageInfo(7, "notify_set"))                       // bus dev par val
    (message_type::notify_mirror_set,               MessageInfo(7, "notify_mirror_set"))                // bus dev par val
    (message_type::notify_can_acquire_write_access, MessageInfo(1, "notify_can_acquire_write_access"))  // bool
    (message_type::notify_mrc_status,               MessageInfo(1, "notify_mrc_status"))
    ;
  return data;
}

const MessageInfo &get_message_info(message_type::MessageType type)
{
  const MessageInfoMap &info_map(get_message_info_map());
  MessageInfoMap::const_iterator it = info_map.find(type);
  if (it != info_map.end())
    return it->second;
  BOOST_THROW_EXCEPTION(std::runtime_error("Unhandled message type"));
}

typedef std::map<error_type::ErrorType, const char *> ErrorInfoMap;

const ErrorInfoMap &get_error_info_map()
{
  static ErrorInfoMap data = boost::assign::map_list_of
    (error_type::unknown_error        , "unknown_error")
    (error_type::invalid_message_type , "invalid_message_type")
    (error_type::invalid_message_size , "invalid_message_size")
    (error_type::bus_out_of_range     , "bus_out_of_range")
    (error_type::dev_out_of_range     , "dev_out_of_range")
    (error_type::mrc_no_response      , "mrc_no_response")
    (error_type::mrc_comm_timeout     , "mrc_comm_timeout")
    (error_type::mrc_comm_error       , "mrc_comm_error")
    (error_type::silenced             , "silenced")
    (error_type::mrc_connect_error    , "mrc_connect_error")
    (error_type::permission_denied    , "permission_denied")
    (error_type::mrc_parse_error      , "mrc_parse_error")
    (error_type::mrc_address_conflict , "mrc_address_conflict")
    (error_type::read_out_of_bounds   , "read_out_of_bounds")
    ;
  return data;
}

const char *get_error_info(error_type::ErrorType type)
{
  const ErrorInfoMap &info_map(get_error_info_map());
  ErrorInfoMap::const_iterator it = info_map.find(type);
  if (it != info_map.end())
    return it->second;
  BOOST_THROW_EXCEPTION(std::runtime_error("Unhandled error type"));
}

} // anon namespace

bool Message::operator==(const Message &o) const
{
  return type == o.type &&
    bus == o.bus &&
    dev == o.dev &&
    par == o.par &&
    val == o.val &&
    error_value == o.error_value &&
    bool_value == o.bool_value &&
    bus_data == o.bus_data;
}

bool Message::operator==(const MessagePtr &o) const
{
  return (*this == *o);
}

bool Message::is_mrc1_command() const
{
  switch (type) {
    case message_type::request_scanbus:
    case message_type::request_rc_on:
    case message_type::request_rc_off:
    case message_type::request_reset:
    case message_type::request_copy:
    case message_type::request_read:
    case message_type::request_set:
    case message_type::request_mirror_read:
    case message_type::request_mirror_set:
      return true;
    default:
      break;
  }
  return false;
}

bool Message::is_mrc1_write_command() const
{
  switch (type) {
    case message_type::request_rc_on:
    case message_type::request_rc_off:
    case message_type::request_reset:
    case message_type::request_copy:
    case message_type::request_set:
    case message_type::request_mirror_set:
      return true;
    default:
      break;
  }
  return false;
}

std::string Message::get_mrc1_command_string() const
{
  /* boost::format prints unit8_t as a char which can result in the output of
   * control characters depending on the value. The workaround is to cast the
   * values to unsigned int and use those for the formatting operation. */
  unsigned int ibus = static_cast<unsigned int>(bus);
  unsigned int idev = static_cast<unsigned int>(dev);
  unsigned int ipar = static_cast<unsigned int>(par);
  unsigned int ilen = static_cast<unsigned int>(len);

  switch (type) {
    case message_type::request_scanbus:
      return boost::str(boost::format("SC %1%") % ibus);
    case message_type::request_rc_on:
      return boost::str(boost::format("ON %1% %2%") % ibus % idev);
    case message_type::request_rc_off:
      return boost::str(boost::format("OFF %1% %2%") % ibus % idev);
    case message_type::request_reset:
      return boost::str(boost::format("RST %1% %2%") % ibus % idev);
    case message_type::request_copy:
      return boost::str(boost::format("CP %1% %2%") % ibus % idev);
    case message_type::request_read:
      return boost::str(boost::format("RE %1% %2% %3%") % ibus % idev % ipar);
    case message_type::request_mirror_read:
      return boost::str(boost::format("RM %1% %2% %3%") % ibus % idev % ipar);
    case message_type::request_set:
      return boost::str(boost::format("SE %1% %2% %3% %4%") % ibus % idev % ipar % val);
    case message_type::request_mirror_set:
      return boost::str(boost::format("SM %1% %2% %3% %4%") % ibus % idev % ipar % val);
    case message_type::request_read_multi:
      return boost::str(boost::format("RB %1% %2% %3% %4%") % ibus % idev % ipar % ilen);

    default:
      BOOST_THROW_EXCEPTION(std::runtime_error("not a mrc command request"));
  }
}

std::vector<unsigned char> Message::serialize() const
{
  std::vector<unsigned char> ret;
  boost::uint32_t net_value;

  ret.push_back(type);

  switch (type) {
    case message_type::request_scanbus:
    case message_type::response_scanbus:
      ret.push_back(bus);
      break;

    case message_type::request_read:
    case message_type::request_mirror_read:
      ret.push_back(bus);
      ret.push_back(dev);
      ret.push_back(par);
      break;

    case message_type::request_set:
    case message_type::request_mirror_set:
    case message_type::response_read:
    case message_type::response_set:
    case message_type::response_mirror_read:
    case message_type::response_mirror_set:
    case message_type::notify_set:
    case message_type::notify_mirror_set:
      ret.push_back(bus);
      ret.push_back(dev);
      ret.push_back(par);

      net_value = htonl(*reinterpret_cast<const boost::uint32_t *>(&val));

      for (size_t i=0; i<sizeof(net_value); ++i)
        ret.push_back(reinterpret_cast<unsigned char *>(&net_value)[i]);

      break;

    case message_type::response_read_multi:
      ret.push_back(bus);
      ret.push_back(dev);
      ret.push_back(par);

      BOOST_FOREACH(boost::int32_t value, values) {
        net_value = htonl(*reinterpret_cast<const boost::uint32_t *>(&value));

        for (size_t i=0; i<sizeof(net_value); ++i)
          ret.push_back(reinterpret_cast<unsigned char *>(&net_value)[i]);
      }

      break;

    case message_type::request_rc_on:
    case message_type::request_rc_off:
    case message_type::request_reset:
    case message_type::request_copy:
      ret.push_back(bus);
      ret.push_back(dev);
      break;

    case message_type::request_set_silent_mode:
    case message_type::response_bool:
    case message_type::notify_write_access:
    case message_type::notify_silent_mode:
    case message_type::notify_can_acquire_write_access:
      ret.push_back(bool_value);
      break;

    case message_type::response_error:
      ret.push_back(error_value);
      break;

    case message_type::response_mrc_status:
    case message_type::notify_mrc_status:
      ret.push_back(status);
      break;

    /* Mention no-op types here to avoid compiler warnings. */
    case message_type::request_has_write_access:
    case message_type::request_acquire_write_access:
    case message_type::request_release_write_access:
    case message_type::request_in_silent_mode :
    case message_type::request_force_write_access:
    case message_type::request_mrc_status:
    case message_type::request_read_multi:
      break;
  }

  if (type == message_type::response_scanbus) {
    for (int i=0; i<16; ++i) {
      ret.push_back(bus_data[i].first);
      ret.push_back(bus_data[i].second);
    }
  }

  return ret;
}

MessagePtr Message::deserialize(const std::vector<unsigned char> &data)
{
  if (data.empty())
    BOOST_THROW_EXCEPTION(std::runtime_error("empty message data"));

  message_type::MessageType type = static_cast<message_type::MessageType>(data[0]);

  ssize_t expected_size = get_message_size(type);

  if (expected_size > 0 && data.size() != static_cast<size_t>(expected_size)) {
    BOOST_THROW_EXCEPTION(std::runtime_error("wrong message size"));
  }

  MessagePtr ret(boost::make_shared<Message>());
  ret->type = type;

  switch (ret->type) {
    case message_type::request_scanbus:
    case message_type::response_scanbus:
      ret->bus = data[1];
      break;

    case message_type::request_read:
    case message_type::request_mirror_read:
      ret->bus = data[1];
      ret->dev = data[2];
      ret->par = data[3];
      break;

    case message_type::request_set:
    case message_type::request_mirror_set:
    case message_type::response_read:
    case message_type::response_mirror_read: 
    case message_type::response_set: 
    case message_type::response_mirror_set:  
    case message_type::notify_set:
    case message_type::notify_mirror_set:
      ret->bus = data[1];
      ret->dev = data[2];
      ret->par = data[3];

      for (size_t i=0; i<sizeof(ret->val); ++i)
        reinterpret_cast<unsigned char *>(&ret->val)[i] = data[i+4];

      ret->val = ntohl(*reinterpret_cast<const boost::uint32_t *>(&ret->val));

      break;

    case message_type::request_read_multi:
      ret->bus = data[1];
      ret->dev = data[2];
      ret->par = data[3];
      ret->len = data[4];
      break;

    case message_type::request_rc_on:
    case message_type::request_rc_off:
    case message_type::request_reset:
    case message_type::request_copy:
      ret->bus = data[1];
      ret->dev = data[2];
      break;

    case message_type::response_bool:
    case message_type::notify_write_access:
    case message_type::notify_silent_mode:
    case message_type::notify_can_acquire_write_access:
    case message_type::request_set_silent_mode:
      ret->bool_value = data[1];
      break;

    case message_type::response_error:
      ret->error_value = static_cast<error_type::ErrorType>(data[1]);
      break;

    case message_type::response_mrc_status:
    case message_type::notify_mrc_status:
      ret->status = static_cast<mrc_status::Status>(data[1]);
      break;

    /* Mention no-op types here to avoid compiler warnings. */
    case message_type::request_in_silent_mode:
    case message_type::request_acquire_write_access:
    case message_type::request_has_write_access:
    case message_type::request_release_write_access:
    case message_type::request_force_write_access:
    case message_type::request_mrc_status:
    case message_type::response_read_multi:
      break;
  }

  if (ret->type == message_type::response_scanbus) {
    for (int i=0; i<32; i+=2) {
      boost::uint8_t idc = data[i+2];
      bool     on = data[i+3];
      ret->bus_data[i/2] = std::make_pair(idc, on);
    }
  }

  return ret;
}


ssize_t Message::get_message_size(message_type::MessageType type)
{
  ssize_t ret = get_message_info(type).size;
  return ret < 0 ? ret : ret + 1; // add one byte for the type field
}

std::string Message::get_info_string() const
{
  const MessageInfo &info(get_message_info(type));
  if (type == message_type::response_error)
    return boost::str(boost::format("%1% (%2%)") % info.type_string % get_error_info(error_value));

  if (is_mrc1_command())
    return boost::str(boost::format("%1% (%2%)") % info.type_string % get_mrc1_command_string());

  return info.type_string;
}

MessagePtr MessageFactory::make_scanbus_response(boost::uint8_t bus, const Message::ScanbusData &bus_data)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type     = message_type::response_scanbus;
  ret->bus      = bus;
  ret->bus_data = bus_data;
  return ret;
}

MessagePtr MessageFactory::make_read_request(boost::uint8_t bus, boost::uint8_t dev,
    boost::uint8_t par, bool mirror)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type = mirror ? message_type::request_mirror_read : message_type::request_read;
  ret->bus  = bus;
  ret->dev  = dev;
  ret->par  = par;
  return ret;
}

MessagePtr MessageFactory::make_read_response(boost::uint8_t bus, boost::uint8_t dev,
    boost::uint8_t par, boost::int32_t val, bool mirror)
{
  return make_read_or_set_response(
      mirror ? message_type::request_mirror_read : message_type::request_read,
      bus, dev, par, val);
}

MessagePtr MessageFactory::make_set_response(boost::uint8_t bus, boost::uint8_t dev,
    boost::uint8_t par, boost::int32_t val, bool mirror)
{
  return make_read_or_set_response(
      mirror ? message_type::request_mirror_set : message_type::request_mirror_read,
      bus, dev, par, val);
}

MessagePtr MessageFactory::make_read_or_set_response(message_type::MessageType request_type,
    boost::uint8_t bus, boost::uint8_t dev, boost::uint8_t par, boost::int32_t val)
{
  MessagePtr ret(boost::make_shared<Message>());
  switch (request_type) {
    case message_type::request_set:
      ret->type = message_type::response_set;
      break;
    case message_type::request_mirror_set:
      ret->type = message_type::response_mirror_set;
      break;
    case message_type::request_read:
      ret->type = message_type::response_read;
      break;
    case message_type::request_mirror_read:
      ret->type = message_type::response_mirror_read;
      break;
    default:
        BOOST_THROW_EXCEPTION(std::runtime_error("make_read_or_set_response: unexpected request MessageType"));
  }

  ret->bus = bus;
  ret->dev = dev;
  ret->par = par;
  ret->val = val;
  return ret;
}

MessagePtr MessageFactory::make_read_multi_response(boost::uint8_t bus, boost::uint8_t dev,
    boost::uint8_t start_param, const std::vector<boost::int32_t> &values)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type   = message_type::response_read_multi;
  ret->bus    = bus;
  ret->dev    = dev;
  ret->par    = start_param;
  ret->values = values;
  return ret;
}

MessagePtr MessageFactory::make_bool_response(bool bool_value)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type = message_type::response_bool;
  ret->bool_value = bool_value;
  return ret;
}

MessagePtr MessageFactory::make_error_response(error_type::ErrorType error)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type        = message_type::response_error;
  ret->error_value = error;
  return ret;
}

MessagePtr MessageFactory::make_write_access_notification(bool has_write_access)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type        = message_type::notify_write_access;
  ret->bool_value  = has_write_access;
  return ret;
}

MessagePtr MessageFactory::make_silent_mode_notification(bool silence_active)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type        = message_type::notify_silent_mode;
  ret->bool_value  = silence_active;
  return ret;
}

MessagePtr MessageFactory::make_parameter_set_notification(boost::uint8_t bus, boost::uint8_t dev,
    boost::uint8_t par, boost::int32_t value, bool mirror)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type        = mirror ? message_type::notify_mirror_set : message_type::notify_set;
  ret->bus = bus;
  ret->dev = dev;
  ret->par = par;
  ret->val = value;
  return ret;
}

MessagePtr MessageFactory::make_can_acquire_write_access_notification(bool can_acquire)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type        = message_type::notify_silent_mode;
  ret->bool_value  = can_acquire;
  return ret;
}

MessagePtr MessageFactory::make_mrc_status_changed_notification(const mrc_status::Status &status)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type   = message_type::notify_mrc_status;
  ret->status = status;
  return ret;
}

MessagePtr MessageFactory::make_mrc_status_response(const mrc_status::Status &status)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type   = message_type::response_mrc_status;
  ret->status = status;
  return ret;
}

} // namespace mesycontrol
