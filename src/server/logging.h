#ifndef UUID_4a9c83f4_2918_46db_82e0_ef1e0fa13dd6
#define UUID_4a9c83f4_2918_46db_82e0_ef1e0fa13dd6

#include "config.h"
#include <boost/log/trivial.hpp>
#include <boost/log/sources/severity_channel_logger.hpp>
#include <boost/log/keywords/channel.hpp>

namespace mesycontrol
{
namespace log
{

namespace lvl      = boost::log::trivial;
namespace keywords = boost::log::keywords;

typedef boost::log::sources::severity_channel_logger_mt<lvl::severity_level> Logger;

void init_logging();

}
}

#endif
