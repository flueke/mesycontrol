#include "config.h"
#include <boost/asio.hpp>
#include <boost/bind.hpp>
#include <boost/program_options/cmdline.hpp>
#include <boost/program_options/option.hpp>
#include <boost/program_options/options_description.hpp>
#include <boost/program_options/parsers.hpp>
#include <boost/program_options/value_semantic.hpp>
#include <boost/program_options/variables_map.hpp>
#include <boost/make_shared.hpp>
#include <boost/ref.hpp>
#include "mrc1_connection.h"
#include "request_dispatcher.h"
#include "tcp_server.h"
#include "git_sha1.h"

/* TODO
 * - scanbus 3 shuts down the mrc connection cause of a timeout. fix this!
 *   the command 'sc 3' results in only one line of output: 'ERROR!' no other
 *   output is generated.
 * - tcp connection timeouts
 * - request dispatch: queue requests, check mrc1 status, send commands to mrc1, call response handler
 *   The dispatcher knows the MRC1Connection instance and acts as a
 *   response_handler and registers itself with the tcp server instance as the
 *   request_handler
 * - logging
 * - exception safety
 */

namespace po = boost::program_options;
using namespace mesycontrol;

enum exit_codes
{
  exit_success = 0,
  exit_options_error = 1,         // indicates wrong or missing options
  exit_address_in_use = 2,
  exit_address_not_available = 3,
  exit_permission_denied = 4,
  exit_bad_listen_address = 5,
  exit_unknown_error = 127
};

int main(int argc, char *argv[])
{
  po::options_description options("Command line options");
  options.add_options()
    ("version,V", "print version and exit")
    ("help,h",    "print help message and exit")
    
    ("listen-address", po::value<std::string>()->default_value("::"),
     "server listening address (IPv4 in dotted decimal form or IPv6 in hex notation)")

    ("listen-port", po::value<unsigned short>()->default_value(23000),
     "server listening port")

    ("mrc-serial-port", po::value<std::string>(),
     "connect to MRC using the given serial port (conflicts with mrc-host)")

    ("mrc-baud-rate", po::value<unsigned int>()->default_value(9600),
     "baud rate to use for the serial port")

    ("mrc-host", po::value<std::string>(),
     "connect to MRC using a TCP connection to the given host (conflicts with mrc-serial-port)")

    ("mrc-port", po::value<unsigned short>()->default_value(4001),
     "port number to connect to if using TCP")
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
    std::cout << options << std::endl;
    return exit_success;
  }

  if (option_map.count("version")) {
    std::cout << "mesycontrol_server - git revision " << g_GIT_SHA1 << std::endl;
    return exit_success;
  }

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

  RequestDispatcher dispatcher(mrc1_connection);

  boost::shared_ptr<TCPServer> tcp_server;

  try {
    namespace ip = boost::asio::ip;

    ip::tcp::endpoint listen_endpoint(
        ip::address::from_string(option_map["listen-address"].as<std::string>()),
        option_map["listen-port"].as<unsigned short>());

    tcp_server = boost::make_shared<TCPServer>(
        boost::ref(io_service),
        listen_endpoint,
        boost::bind(&RequestDispatcher::dispatch, &dispatcher, _1, _2));

  } catch (const boost::system::system_error &e) {
    std::cerr << "Failed starting TCP server component: " << e.what() << std::endl;

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

  mrc1_connection->start();
  io_service.run();

  return exit_success;
}
