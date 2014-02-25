#include <boost/asio.hpp>
#include <boost/program_options/cmdline.hpp>
#include <boost/program_options/option.hpp>
#include <boost/program_options/options_description.hpp>
#include <boost/program_options/parsers.hpp>
#include <boost/program_options/value_semantic.hpp>
#include <boost/program_options/variables_map.hpp>
#include "mrc1_connection.h"

namespace po = boost::program_options;

enum exit_codes
{
  exit_success = 0,
  exit_error_options = 1,  // indicates wrong or missing options
  exit_error_listen = 2    // indicates that listening for tcp connections failed
};

int main(int argc, char *argv[])
{
  po::options_description options("Command line options");
  options.add_options()
    ("version,V", "print version and exit")
    ("help,h",    "print help message and exit")
    
    ("mrc-serial-port", po::value<std::string>(),
     "connect to MRC using the given serial port")

    ("mrc-baud-rate", po::value<unsigned int>()->default_value(9600),
     "baud rate to use for the serial port")

    ("mrc-hostname", po::value<std::string>(),
     "connect to MRC using a TCP connection to the given host")

    ("mrc-port", po::value<unsigned short>()->default_value(4001),
     "port number to connect to if using TCP")

    ("listen-port", po::value<unsigned short>()->default_value(23000),
     "local listening port")
    ;

  po::variables_map option_map;

  try {
    po::store(po::parse_command_line(argc, argv, options), outmap);
    po::notify(outmap);
  } catch (const po::error &e) {
    std::cerr << "Error parsing command line: " << e.what() << std::endl;
    return exit_error_options;
  }

  if (option_map.count("help")) {
    std::cout << options << std::endl;
    return 0;
  }

  if (option_map.count("version")) {
    std::cout << "mesycontrol_server - revision " << MESYCONTROL_GIT_REVISION << std::endl;
    return 0;
  }

  boost::asio::io_service io_service;
#if 0
  boost::shared_ptr<MRC1Connection> mrc1_connection;

  if (use_serial) {
    mrc1_connection = make_shared<MRC1SerialConnection>(boost::ref(io_service), serial_device, baud_rate);
  } else if (use_tcp) {
    mrc1_connection = make_shared<MRC1TCPConnection>(boost::ref(io_service, mrc1_host, mrc1_port));
  } 


  

  Server server;
  return Server.run();
#endif
  return 0;
}
