#include "config.h"

#include <boost/asio.hpp>
#include <boost/assign.hpp>
#include <boost/bind.hpp>
#include <boost/make_shared.hpp>
#include <boost/program_options/cmdline.hpp>
#include <boost/program_options/option.hpp>
#include <boost/program_options/options_description.hpp>
#include <boost/program_options/parsers.hpp>
#include <boost/program_options/value_semantic.hpp>
#include <boost/program_options/variables_map.hpp>
#include <boost/ref.hpp>

#include "accumulator.hpp"
#include "mrc1_connection.h"
#include "tcp_server.h"
#include "git_sha1.h"
#include "logging.h"

namespace po = boost::program_options;
using namespace mesycontrol;

enum exit_code
{
  exit_success                = 0,
  exit_options_error          = 1, // indicates wrong or missing options
  exit_address_in_use         = 2,
  exit_address_not_available  = 3,
  exit_permission_denied      = 4,
  exit_bad_listen_address     = 5,
  exit_unknown_error          = 127
};

std::string to_string(exit_code code)
{
  static std::map<exit_code, std::string> strings = boost::assign::map_list_of
    (exit_success,                  "success")
    (exit_options_error ,           "invalid options given")
    (exit_address_in_use,           "listen address in use")
    (exit_address_not_available,    "listen address not available")
    (exit_permission_denied,        "permission denied")
    (exit_bad_listen_address,       "bad listen address")
    (exit_unknown_error,            "unknown error");

    std::map<exit_code, std::string>::const_iterator it = strings.find(code);

    if (it != strings.end())
      return it->second;

    return boost::lexical_cast<std::string>(static_cast<int>(code));
}

int main(int argc, char *argv[])
{
  po::options_description options("Command line options");
  options.add_options()
    ("mrc-serial-port", po::value<std::string>(),
     "Connect to MRC using the given serial port (conflicts with mrc-host).")

    ("mrc-baud-rate", po::value<unsigned int>()->default_value(0),
     "Baud rate to use for the serial port. 0 means auto-detect.")

    ("mrc-host", po::value<std::string>(),
     "Connect to MRC using a TCP connection to the given host (conflicts with mrc-serial-port).")

    ("mrc-port", po::value<unsigned short>()->default_value(4001),
     "Port number to connect to if using TCP.")

    ("listen-address", po::value<std::string>()->default_value("::"),
     "Server listening address (IPv4 in dotted decimal form or IPv6 in hex notation).")

    ("listen-port", po::value<unsigned short>()->default_value(23000),
     "Server listening port.")

    ("verbose,v", accumulator<int>(),
     "Increase verbosity level (can be used multiple times).")

    ("quiet,q", accumulator<int>(),
     "Decrease verbosity level (can be used multiple times).")

    ("version,V", "Print version and exit.")
    ("help,h",    "Print help message and exit.")
    ;

  po::variables_map option_map;

  try {
    po::store(po::parse_command_line(argc, argv, options), option_map);
    po::notify(option_map);
  } catch (const po::error &e) {
    std::cerr << "Error parsing command line: " << e.what() << std::endl;
    return exit_options_error;
  }

  if (option_map.count("help")) {
    std::cout << "mesycontrol_server version " << g_GIT_VERSION << std::endl;
    std::cout << std::endl << options << std::endl;
    std::cout << "Examples:"
      << std::endl << "$ mesycontrol_server --mrc-serial-port /dev/ttyUSB0"
      << std::endl << "  -> Use the first USB serial port and auto-detect the baud rate."
      << std::endl
      << std::endl << "$ mesycontrol_server --mrc-host example.com --mrc-port 8192"
      << std::endl << "  -> Connect to the serial server listening on example.com:8192."
      << std::endl
      << std::endl << "$ mesycontrol_server --mrc-serial-port /dev/ttyUSB0 --listen-address 127.0.0.1"
      << std::endl << "  -> Serial connection but make the server listen only on the loopback device."
      << std::endl;
      ;
    return exit_success;
  }

  if (option_map.count("version")) {
    std::cout << "mesycontrol_server version " << g_GIT_VERSION << std::endl;
    return exit_success;
  }

  log::init_logging();
  log::Logger logger(log::keywords::channel="main");

  log::set_verbosity(option_map["verbose"].as<int>() - option_map["quiet"].as<int>());

  if (option_map.count("mrc-serial-port") && option_map.count("mrc-host")) {
    std::cerr << "Error: both --mrc-serial-port and --mrc-host given" << std::endl;
    return exit_options_error;
  }

  boost::asio::io_service io_service;
  boost::shared_ptr<MRC1Connection> mrc1_connection;

  if (option_map.count("mrc-serial-port")) {
    mrc1_connection = boost::make_shared<MRC1SerialConnection>(
        boost::ref(io_service),
        option_map["mrc-serial-port"].as<std::string>(),
        option_map["mrc-baud-rate"].as<unsigned int>());
  } else if (option_map.count("mrc-host")) {
    mrc1_connection = boost::make_shared<MRC1TCPConnection>(
        boost::ref(io_service),
        option_map["mrc-host"].as<std::string>(),
        option_map["mrc-port"].as<unsigned short>());
  } else {
    std::cerr << "Error: neither --mrc-serial-port nor --mrc-host given" << std::endl;
    return exit_options_error;
  }

  MRC1RequestQueue mrc1_request_queue(mrc1_connection);
  TCPConnectionManager connection_manager(mrc1_request_queue);
  boost::shared_ptr<TCPServer> tcp_server;

  try {
    namespace ip = boost::asio::ip;

    ip::tcp::endpoint listen_endpoint(
        ip::address::from_string(option_map["listen-address"].as<std::string>()),
        option_map["listen-port"].as<unsigned short>());

    tcp_server = boost::make_shared<TCPServer>(
        boost::ref(io_service),
        listen_endpoint,
        boost::ref(connection_manager));
  } catch (const boost::system::system_error &e) {
    std::cerr << "Error: Failed starting TCP server component: " << e.what() << std::endl;

    namespace errc = boost::system::errc;
    const boost::system::error_code ec(e.code());

    if (ec == errc::address_in_use)
      return exit_address_in_use;

    if (ec == errc::address_not_available)
      return exit_address_not_available;

    if (ec == errc::permission_denied)
      return exit_permission_denied;

    if (ec == errc::invalid_argument)
      return exit_bad_listen_address;

    return exit_unknown_error;
  }

  boost::asio::signal_set signal_set(io_service);
  signal_set.add(SIGINT);
  signal_set.add(SIGTERM);
#ifdef SIGQUIT
  signal_set.add(SIGQUIT);
#endif

  signal_set.async_wait(boost::bind(&MRC1Connection::stop, mrc1_connection));
  signal_set.async_wait(boost::bind(&TCPServer::stop, tcp_server));

  BOOST_LOG_SEV(logger, log::lvl::info) << "Starting MRC1 connection";

  try {
    mrc1_connection->start();
    io_service.run();
  } catch (const std::exception &e) {
    std::cerr << "Error: Unhandled exception from io_service: " << e.what() << std::endl;
    return exit_unknown_error;
  }

  BOOST_LOG_SEV(logger, log::lvl::info) << "mesycontrol_server exiting";

  return exit_success;
}
