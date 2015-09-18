#ifndef UUID_414dcc58_b60c_46ce_aaba_ccba651b8f68
#define UUID_414dcc58_b60c_46ce_aaba_ccba651b8f68

#include <boost/cstdint.hpp>
#include <boost/shared_ptr.hpp>

#include "config.h"
#include "mesycontrol.pb.h"

namespace mesycontrol
{

typedef boost::shared_ptr<proto::Message> MessagePtr;

class MessageFactory
{
  public:
    static MessagePtr make_scanbus_response(boost::uint8_t bus);
    static MessagePtr make_scanbus_request(boost::uint8_t bus);

    static MessagePtr make_read_request(boost::uint8_t bus, boost::uint8_t dev,
        boost::uint8_t par, bool mirror=false);

    static MessagePtr make_read_response(boost::uint8_t bus, boost::uint8_t dev,
        boost::uint8_t par, boost::int32_t val, bool mirror=false);

    static MessagePtr make_set_response(boost::uint8_t bus, boost::uint8_t dev,
        boost::uint8_t par, boost::int32_t val, boost::int32_t requested_value,
        bool mirror=false);

    static MessagePtr make_bool_response(bool bool_value);
    static MessagePtr make_error_response(const proto::ResponseError::ErrorType &error);

    static MessagePtr make_write_access_notification(bool has_write_access, bool can_acquire);

    static MessagePtr make_silent_mode_notification(bool silence_active);

    static MessagePtr make_parameter_set_notification(boost::uint8_t bus, boost::uint8_t dev,
        boost::uint8_t par, boost::int32_t value, boost::int32_t requested_value, bool mirror = false);

    static MessagePtr make_mrc_status_response(const proto::MRCStatus::Status &status,
        const std::string &info=std::string(), const std::string &version=std::string(),
        bool has_read_multi=false);

    static MessagePtr make_mrc_status_notification(const proto::MRCStatus::Status &status,
        const std::string &info=std::string(), const std::string &version=std::string(),
        bool has_read_multi=false);

    static MessagePtr make_read_multi_response(boost::uint8_t bus, boost::uint8_t dev,
        boost::uint8_t start_param, const std::vector<boost::int32_t> &values = std::vector<boost::int32_t>());
};

bool is_mrc1_command(const MessagePtr &msg);
bool is_mrc1_write_command(const MessagePtr &msg);
std::string get_mrc1_command_string(const MessagePtr &msg);
std::string get_message_info(const MessagePtr &msg);

} // namespace mesycontrol

#endif
