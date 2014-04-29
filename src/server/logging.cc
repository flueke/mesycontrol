#include "logging.h"
#include <boost/date_time/posix_time/posix_time_types.hpp>
#include <boost/log/expressions/formatters.hpp>
#include <boost/log/expressions.hpp>
#include <boost/log/sources/record_ostream.hpp>
#include <boost/log/sources/severity_logger.hpp>
#include <boost/log/support/date_time.hpp>
#include <boost/log/utility/setup/common_attributes.hpp>
#include <boost/log/utility/setup/console.hpp>
#include <boost/log/utility/setup/file.hpp>

namespace mesycontrol
{
namespace log
{

namespace expr = boost::log::expressions;

void init_logging()
{
  boost::log::register_simple_formatter_factory<
    boost::log::trivial::severity_level, char>("Severity");

  boost::log::add_common_attributes();

  boost::log::add_console_log(
      std::cout,
      keywords::format = expr::stream
        << "[" << expr::format_date_time< boost::posix_time::ptime >("TimeStamp", "%y/%m/%d %H:%M:%S.%f")
        << "] [" << std::setw(7) << boost::log::trivial::severity << "] "
        << expr::attr<std::string>("Channel") << ": " << expr::smessage);
}

}
}
