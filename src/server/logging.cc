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

namespace expr  = boost::log::expressions;
namespace sinks = boost::log::sinks;

void init_logging()
{
  boost::log::register_simple_formatter_factory<
    boost::log::trivial::severity_level, char>("Severity");

  boost::log::add_common_attributes();

  boost::shared_ptr<
    sinks::synchronous_sink<sinks::text_ostream_backend>
    > sink = boost::log::add_console_log(
        std::cout,
        keywords::format = expr::stream
          << "[" << expr::format_date_time< boost::posix_time::ptime >("TimeStamp", "%y/%m/%d %H:%M:%S.%f")
          << "] [" << std::setw(7) << boost::log::trivial::severity << "] "
          << expr::attr<std::string>("Channel") << ": " << expr::smessage);

  sink->locked_backend()->auto_flush(true);

  boost::log::core::get()->set_filter(
      boost::log::trivial::severity >= boost::log::trivial::info);
}

void set_verbosity(int verbosity)
{
  int sev;

  sev = std::max(0, boost::log::trivial::info - verbosity);
  sev = std::min(sev, static_cast<int>(boost::log::trivial::fatal));

  boost::log::trivial::severity_level
    new_severity = static_cast<boost::log::trivial::severity_level>(sev);

  boost::log::core::get()->set_filter(
      boost::log::trivial::severity >= new_severity);
}

}
}
