#include <boost/assign.hpp>
#include <boost/format.hpp>
#include <boost/make_shared.hpp>
#include <map>
#include <stdexcept>
#include <mesycontrol/protocol.h>

namespace mesycontrol
{

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

std::string Message::get_mrc1_command_string() const
{
  /* boost::format prints unit8_t as a char which can result in the output of
   * control characters depending on the value. The workaround is to cast the
   * values to unsigned int and use those for the formatting operation. */
  unsigned int ibus = static_cast<unsigned int>(bus);
  unsigned int idev = static_cast<unsigned int>(dev);
  unsigned int ipar = static_cast<unsigned int>(par);
  unsigned int ival = static_cast<unsigned int>(val);

  switch (type) {
    case message_type::request_scanbus:
      return boost::str(boost::format("SC %1%\r") % ibus);
    case message_type::request_rc_on:
      return boost::str(boost::format("ON %1% %2%\r") % ibus % idev);
    case message_type::request_rc_off:
      return boost::str(boost::format("OFF %1% %2%\r") % ibus % idev);
    case message_type::request_reset:
      return boost::str(boost::format("RST %1% %2%\r") % ibus % idev);
    case message_type::request_copy:
      return boost::str(boost::format("CP %1% %2%\r") % ibus % idev);
    case message_type::request_read:
      return boost::str(boost::format("RE %1% %2% %3%\r") % ibus % idev % ipar);
    case message_type::request_mirror_read:
      return boost::str(boost::format("RM %1% %2% %3%\r") % ibus % idev % ipar);
    case message_type::request_set:
      return boost::str(boost::format("SE %1% %2% %3% %4%\r") % ibus % idev % ipar % ival);
    case message_type::request_mirror_set:
      return boost::str(boost::format("SM %1% %2% %3% %4%\r") % ibus % idev % ipar % ival);

    default:
      BOOST_THROW_EXCEPTION(std::runtime_error("not a mrc command request"));
  }
}

std::vector<unsigned char> Message::serialize() const
{
  std::vector<unsigned char> ret;

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
      ret.push_back(bus);
      ret.push_back(dev);
      ret.push_back(par);
      ret.push_back((val >> 8) & 0xFF);
      ret.push_back(val);
      break;

    case message_type::request_rc_on:
    case message_type::request_rc_off:
    case message_type::request_reset:
    case message_type::request_copy:
      ret.push_back(bus);
      ret.push_back(dev);
      break;

    case message_type::request_is_master:
    case message_type::request_acquire_master:
    case message_type::request_in_silent_mode :
      break;

    case message_type::request_set_silent_mode:
    case message_type::response_bool:
    case message_type::notify_master_state:
    case message_type::notify_silent_mode:
      ret.push_back(bool_value);
      break;

    case message_type::response_error:
      ret.push_back(error_value);
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

  if (data.size() != get_message_size(type)) {
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
      ret->bus = data[1];
      ret->dev = data[2];
      ret->par = data[3];
      ret->val = (data[4] << 8 | data[5]);
      break;

    case message_type::request_rc_on:
    case message_type::request_rc_off:
    case message_type::request_reset:
    case message_type::request_copy:
      ret->bus = data[1];
      ret->dev = data[2];
      break;

    case message_type::response_bool:
    case message_type::notify_master_state:
    case message_type::notify_silent_mode:
    case message_type::request_set_silent_mode:
      ret->bool_value = data[1];
      break;

    case message_type::response_error:
      ret->error_value = static_cast<error_type::ErrorType>(data[1]);
      break;

    case message_type::request_in_silent_mode:
    case message_type::request_acquire_master:
    case message_type::request_is_master:
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

size_t Message::get_message_size(message_type::MessageType type)
{
  static std::map<message_type::MessageType, size_t> sizes = boost::assign::map_list_of
    (message_type::request_scanbus,         1) // bus
    (message_type::request_rc_on,           2) // bus dev
    (message_type::request_rc_off,          2) // bus dev
    (message_type::request_reset,           2) // bus dev
    (message_type::request_copy,            2) // bus dev
    (message_type::request_read,            3) // bus dev par
    (message_type::request_mirror_read,     3) // bus dev par
    (message_type::request_set,             5) // bus dev par val
    (message_type::request_mirror_set,      5) // bus dev par val

    (message_type::request_is_master,       0)
    (message_type::request_acquire_master,  0)
    (message_type::request_in_silent_mode,  0)
    (message_type::request_set_silent_mode, 1) // bool

    (message_type::response_scanbus,       33) // bus (idc,bool){16}
    (message_type::response_read,           5) // bus dev par val
    (message_type::response_set,            5) // bus dev par val
    (message_type::response_mirror_read,    5) // bus dev par val
    (message_type::response_mirror_set,     5) // bus dev par val

    (message_type::response_error,          1) // error value
    (message_type::response_bool,           1) // bool value
    ;

    std::map<message_type::MessageType, size_t>::const_iterator it = sizes.find(type);

    if (it != sizes.end()) {
      return it->second + 1; // add one byte for the type field
    }

    return 0;
}

MessagePtr Message::make_scanbus_request(boost::uint8_t bus)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type = message_type::request_scanbus;
  ret->bus  = bus;
  return ret;
}

MessagePtr Message::make_read_request(boost::uint8_t bus, boost::uint8_t dev, boost::uint8_t par, bool mirror)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type = mirror ? message_type::request_mirror_read : message_type::request_read;
  ret->bus  = bus;
  ret->dev  = dev;
  ret->par  = par;
  return ret;
}

MessagePtr Message::make_set_request(boost::uint8_t bus, boost::uint8_t dev, boost::uint8_t par, boost::uint16_t value, bool mirror)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type = mirror ? message_type::request_mirror_set : message_type::request_set;
  ret->bus  = bus;
  ret->dev  = dev;
  ret->par  = par;
  ret->val  = value;
  return ret;
}

MessagePtr Message::make_set_rc_request(boost::uint8_t bus, boost::uint8_t dev, bool on)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type = on ? message_type::request_rc_on : message_type::request_rc_off;
  ret->bus  = bus;
  ret->dev  = dev;
  return ret;
}

MessagePtr Message::make_reset_request(boost::uint8_t bus, boost::uint8_t dev)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type = message_type::request_reset;
  ret->bus  = bus;
  ret->dev  = dev;
  return ret;
}

MessagePtr Message::make_copy_request(boost::uint8_t bus, boost::uint8_t dev)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type = message_type::request_copy;
  ret->bus  = bus;
  ret->dev  = dev;
  return ret;
}

MessagePtr Message::make_scanbus_response(boost::uint8_t bus, const boost::array<std::pair<boost::uint8_t, bool>, 16> &bus_data)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type     = message_type::response_scanbus;
  ret->bus      = bus;
  ret->bus_data = bus_data;
  return ret;
}

MessagePtr Message::make_read_or_set_response(message_type::MessageType request_type, boost::uint8_t bus, boost::uint8_t dev, boost::uint8_t par, boost::uint16_t val)
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

MessagePtr Message::make_bool_response(bool bool_value)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type = message_type::response_bool;
  ret->bool_value = bool_value;
  return ret;
}

MessagePtr Message::make_error_response(error_type::ErrorType error)
{
  MessagePtr ret(boost::make_shared<Message>());
  ret->type        = message_type::response_error;
  ret->error_value = error;
  return ret;
}

} // namespace mesycontrol
