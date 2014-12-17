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
    notset = 0,
    /* mrc command requests */
    request_scanbus = 1,
    request_read = 2,
    request_set = 3,
    request_mirror_read = 4,
    request_mirror_set = 5,
    request_rc_on = 6,
    request_rc_off = 7,
    request_reset = 8,
    request_copy = 9,
    request_read_multi = 10,

    /* server state related requests */
    request_has_write_access = 20,
    request_acquire_write_access = 21,
    request_release_write_access = 22,
    request_in_silent_mode = 23,
    request_set_silent_mode = 24,
    request_force_write_access = 25,
    request_mrc_status = 26,

    /* mrc command responses */
    response_scanbus = 41,
    response_read = 42,
    response_set = 43,
    response_mirror_read = 44,
    response_mirror_set = 45,
    response_read_multi = 46,

    /* additional response types */
    response_bool = 50,
    response_error = 51,
    response_mrc_status = 52,

    /* notification types */
    notify_write_access             = 60,
    notify_silent_mode              = 61,
    notify_set                      = 62, 
    notify_mirror_set               = 63,
    notify_can_acquire_write_access = 64,
    notify_mrc_status               = 65
  };
} // namespace message_type

namespace error_type
{
  enum ErrorType
  {
    unknown_error               = 0,  // An unknown error occured
    invalid_message_type        = 1,  // An invalid message type was received
    invalid_message_size        = 2,  // Received data size is not equal to the
                                      // expected message size
    bus_out_of_range            = 3,  // Given bus value is out of range
    dev_out_of_range            = 4,  // Given device address value is out of range
    mrc_no_response             = 5,  // No device connected on the given (bus, port) pair
    mrc_comm_timeout            = 6,  // MRC communication timeout
    mrc_comm_error              = 7,  // MRC communication error
    silenced                    = 8,  // Bus access needed but silent mode is active
    mrc_connect_error           = 9,  // Unable to establish the MRC connection
    permission_denied           = 10, // Write permission denied
    mrc_parse_error             = 11, // Error parsing MRC reply
    mrc_address_conflict        = 12, // Bus address conflict
    request_canceled            = 13, // Request canceled (currently client side only)
    read_out_of_bounds          = 14  // A multi read request exceeds the memory range
  };
} // namespace error_type

namespace rc_status
{
  enum RCStatus
  {
    off              = 0,
    on               = 1,
    address_conflict = 2
  };
}

namespace mrc_status
{
  enum Status
  {
    stopped           = 0,
    connecting        = 1,
    connect_failed    = 2,
    initializing      = 3,
    init_failed       = 4,
    running           = 5
  };

} // namespace connection_status

std::string to_string(const mrc_status::Status &status);

struct Message;

typedef boost::shared_ptr<Message> MessagePtr;

/* Very ugly "all-in-one" message structure. */
struct Message
{
  // Scanbus response - 16 pairs of (device id code, rc status).
  // Device id code=0 means no device is connected
  typedef boost::array<std::pair<boost::uint8_t, boost::uint8_t>, 16> ScanbusData;

  message_type::MessageType   type;
  boost::uint8_t              bus;          // bus number [0..1]
  boost::uint8_t              dev;          // device number [0..15]
  boost::uint8_t              par;          // parameter address [0..255]
  boost::int32_t              val;          // value usually in the range [0..65535]
                                            // values returned by the mrc can be negative (mhv4)
  error_type::ErrorType       error_value;  // error messages only
  bool                        bool_value;   // bool messages only
  mrc_status::Status          status;       // mrc status messages only
  ScanbusData                 bus_data;     // scanbus response data
  boost::uint16_t             len;          // length of multi read requests
  std::vector<boost::int32_t> values;       // values of multi read responses

  Message()
    : type(message_type::notset),
    bus(0), dev(0), par(0), val(0),
    error_value(error_type::unknown_error),
    bool_value(false),
    status(mrc_status::stopped),
    len(0)
  {
    std::fill(bus_data.begin(), bus_data.end(),
        std::make_pair(static_cast<boost::uint8_t>(0u), false));
  }

  bool operator==(const Message &o) const;
  bool operator==(const MessagePtr &o) const;

  bool is_mrc1_command() const;
  bool is_mrc1_write_command() const;
  std::string get_mrc1_command_string() const;
  std::vector<unsigned char> serialize() const;

  static MessagePtr deserialize(const std::vector<unsigned char> &data);
  static ssize_t get_message_size(message_type::MessageType type);

  std::string get_info_string() const;
};

class MessageFactory
{
  public:
    static MessagePtr make_scanbus_response(boost::uint8_t bus, const Message::ScanbusData &bus_data);

    static MessagePtr make_read_request(boost::uint8_t bus, boost::uint8_t dev,
        boost::uint8_t par, bool mirror=false);

    static MessagePtr make_read_or_set_response(message_type::MessageType request_type,
        boost::uint8_t bus, boost::uint8_t dev, boost::uint8_t par, boost::int32_t val);

    static MessagePtr make_read_multi_response(boost::uint8_t bus, boost::uint8_t dev,
        boost::uint8_t start_param, const std::vector<boost::int32_t> &values = std::vector<boost::int32_t>());

    static MessagePtr make_bool_response(bool bool_value);
    static MessagePtr make_error_response(error_type::ErrorType error);

    static MessagePtr make_write_access_notification(bool has_write_access);
    static MessagePtr make_silent_mode_notification(bool silence_active);
    static MessagePtr make_parameter_set_notification(boost::uint8_t bus, boost::uint8_t dev,
        boost::uint8_t par, boost::int32_t value, bool mirror = false);
    static MessagePtr make_can_acquire_write_access_notification(bool can_acquire);
    static MessagePtr make_mrc_status_changed_notification(const mrc_status::Status &status);
    static MessagePtr make_mrc_status_response(const mrc_status::Status &status);
};

} // namespace mesycontrol

#endif
