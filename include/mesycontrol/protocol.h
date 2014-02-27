#ifndef UUID_414dcc58_b60c_46ce_aaba_ccba651b8f68
#define UUID_414dcc58_b60c_46ce_aaba_ccba651b8f68

#include "config.h"
#include <boost/array.hpp>
#include <boost/cstdint.hpp>
#include <boost/shared_ptr.hpp>
#include <vector>

namespace mesycontrol
{
namespace message_type
{
  enum MessageType
  {
    request_scanbus = 1,
    request_read = 2,
    request_set = 3,
    request_mirror_read = 4,
    request_mirror_set = 5,

    request_rc_on = 6,
    request_rc_off = 7,
    request_reset = 8,
    request_copy = 9,

    request_is_master = 20,
    request_acquire_master = 21,
    request_in_silent_mode = 22,
    request_set_silent_mode = 23,

    response_scanbus = 41,
    response_read = 42,
    response_set = 43,
    response_mirror_read = 44,
    response_mirror_set = 45,

    response_bool = 60,
    response_error = 61,

    notify_master_state = 80,
    notify_silent_mode = 81,
  };
} // namespace MessageType

namespace error_type
{
  enum ErrorType
  {
    invalid_type        = 1,
    invalid_size        = 2,
    bus_out_of_range    = 3,
    dev_out_of_range    = 4,
    mrc_no_response     = 5,
    mrc_comm_timeout    = 6,
    mrc_comm_error      = 7,
    silenced            = 8,
    unknown_error       = 9,
    mrc_connect_error
  };
} // namespace ErrorType

struct Message;

typedef boost::shared_ptr<Message> MessagePtr;

/* Very ugly "all-in-one" message structure. */
struct Message
{
  message_type::MessageType type;
  boost::uint8_t            bus;
  boost::uint8_t            dev;
  boost::uint8_t            par;
  boost::uint16_t           val;
  error_type::ErrorType     error_value;
  bool                      bool_value;
  boost::array<std::pair<boost::uint8_t, bool>, 16> bus_data;

  Message()
    : bus(0), dev(0), par(0), val(0), error_value(error_type::unknown_error), bool_value(false)
  {}

  bool operator==(const Message &o) const;
  bool operator==(const MessagePtr &o) const;

  bool is_mrc1_command() const;
  std::string get_mrc1_command_string() const;
  std::vector<unsigned char> serialize() const;

  static MessagePtr deserialize(const std::vector<unsigned char> &data);
  static size_t get_message_size(message_type::MessageType type);

  static MessagePtr make_scanbus_request(uint8_t bus);
  static MessagePtr make_read_request(uint8_t bus, uint8_t dev, uint8_t par, bool mirror = false);
  static MessagePtr make_set_request(uint8_t bus, uint8_t dev, uint8_t par, uint16_t value, bool mirror = false);
  static MessagePtr make_set_rc_request(uint8_t bus, uint8_t dev, bool on);
  static MessagePtr make_reset_request(uint8_t bus, uint8_t dev);
  static MessagePtr make_copy_request(uint8_t bus, uint8_t dev);
  static MessagePtr make_is_master_request();
  static MessagePtr make_acquire_master_request();
  static MessagePtr make_silent_mode_status_request();

  static MessagePtr make_scanbus_response(uint8_t bus,
      const boost::array<std::pair<uint8_t, bool>, 16> &bus_data);

  static MessagePtr make_read_or_set_response(message_type::MessageType request_type,
      uint8_t bus, uint8_t dev, uint8_t par, uint16_t val);

  static MessagePtr make_bool_response(bool bool_value);
  static MessagePtr make_error_response(error_type::ErrorType error);
};

} // namespace mesycontrol

#endif
