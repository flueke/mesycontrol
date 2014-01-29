#include <boost/asio.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include <boost/exception/all.hpp>
#include <boost/format.hpp>
#include <boost/program_options/cmdline.hpp>
#include <boost/program_options/config.hpp>
#include <boost/program_options/option.hpp>
#include <boost/program_options/options_description.hpp>
#include <boost/program_options/parsers.hpp>
#include <boost/program_options/positional_options.hpp>
#include <boost/program_options/value_semantic.hpp>
#include <boost/program_options/variables_map.hpp>
#include <boost/program_options/version.hpp>
#include <boost/regex.hpp>
#include <boost/thread/thread.hpp> 
#include <exception>
#include <iostream>
#include <sstream>

using std::cerr;
using std::cout;
using std::endl;
using std::istream;
using std::string;
using std::stringstream;
using boost::format;
namespace asio = boost::asio;
namespace po   = boost::program_options;

typedef asio::serial_port sp;

struct exception_base: virtual std::exception, virtual boost::exception {};
struct runtime_error:  virtual exception_base {};
struct busy_reply:     virtual runtime_error {};
struct error_reply:    virtual runtime_error {};

typedef boost::error_info<struct tag_errinfo_message, string> errinfo_message;

void mrc1_write(asio::serial_port &port, const string &str);
string mrc1_read(asio::serial_port &port);

void aml_write(asio::serial_port &port, const string &str);
string aml_read(asio::serial_port &port);

asio::streambuf g_readbuf;
size_t g_bytesWritten = 0;
size_t g_bytesRead = 0;

string escape_chars(const string &str)
{
   string ret;
   ret.reserve(str.size() * 2);

   for (auto it=begin(str), eit=end(str); it!=eit; ++it) {
      switch (*it) {
         case '\r': ret += "\\r"; break;
         case '\n': ret += "\\n"; break;
         default:   ret += *it;
      }
   }
   return ret;
}

string signed_format(int num)
{
   stringstream ss;
   ss << (num >= 0 ? '+' : '-') << std::abs(num);
   return ss.str();
}

void do_sleep(long msec = 10, bool verbose = true)
{
   if (verbose) {
      cout << "sleeping " << msec << "ms ... ";
      cout.flush();
   }
   boost::this_thread::sleep(boost::posix_time::milliseconds(msec));
   if (verbose) cout << "woke up" << endl;
}

void mrc1_write(asio::serial_port &port, const string &str)
{
   asio::write(port, asio::buffer(str));
   do_sleep(10, false);
   g_bytesWritten += str.size();
}

string mrc1_read(asio::serial_port &port)
{
   /* Use a global buffer here to hold data over multiple calls to mrc1_read. */
   asio::read_until(port, g_readbuf, "\n\r");
   istream is(&g_readbuf);
   string reply;
   std::getline(is, reply, '\r');          // read up to the trailing \r
   g_bytesRead += reply.size();
   return reply.substr(0, reply.size()-1); // remove the trailing \n
}

void mrc1_scanbus(asio::serial_port &port, int bus)
{
   stringstream ss;
   ss << "SC " << bus << "\r";
   mrc1_write(port, ss.str());
   assert(mrc1_read(port) == boost::str(format("mrc-1>SC %1%") % bus));
   assert(mrc1_read(port) == boost::str(format("ID-SCAN BUS %1%:") % bus));

   static const boost::regex re("^\\d+: (-|\\d+, (ON|0FF))$");

   for (int i=0; i<16; ++i) {
      string reply = mrc1_read(port);
      if (!boost::regex_match(reply, re)) {
         cout << "unexpected scanbus reply (i=" << i << "): " << escape_chars(reply) << endl;
         throw 42;
      }
   }
}

void do_mrc1_stuff(asio::serial_port &port)
{
   port.set_option(sp::baud_rate(9600));
   port.set_option(sp::character_size(8));
   port.set_option(sp::parity(sp::parity::none));
   port.set_option(sp::stop_bits(sp::stop_bits::one));
   port.set_option(sp::flow_control(sp::flow_control::none));

#if 0
   sp::native_handle_type fd(port.native_handle());

   if (tcgetattr(fd, &tio) < 0) throw 42;
   tio.c_cc[VMIN]  = 1;
   tio.c_cc[VTIME] = 5;
   if (tcflush(fd, TCIOFLUSH) < 0 || tcsetattr(fd, TCSANOW, &tio) < 0) throw 42;
#endif

   string reply;

   mrc1_write(port, "\r");
   do {
      reply = mrc1_read(port);
   } while (reply != "ERROR!");

   cout << "init sequence complete" << endl;

   for (size_t i=0; i<100; ++i) {
      if (i%10 == 0) {
         cout << "iteration " << i << endl;
      }
      mrc1_scanbus(port, 0);
      mrc1_scanbus(port, 1);
   }
}

void aml_write(asio::serial_port &port, const string &str)
{
   do_sleep(10, false);
   asio::write(port, asio::buffer(str));
   g_bytesWritten += str.size();
}

string aml_read(asio::serial_port &port)
{
   asio::read_until(port, g_readbuf, "\r");
   istream is(&g_readbuf);
   string reply;
   std::getline(is, reply, '\r');
   g_bytesRead += reply.size();
   return reply;
}

void aml_select_axis(asio::serial_port &port, int axis_id)
{
   aml_write(port, boost::str(format("B%1%\r") % axis_id));
   cout << __PRETTY_FUNCTION__ << "reply = " << escape_chars(aml_read(port)) << endl;;
}

void aml_move_relative(asio::serial_port &port, int axis_id, int delta)
{
   aml_select_axis(port, axis_id);
   aml_write(port, signed_format(delta) + "\r");
}

void aml_wait_for_move_finished(asio::serial_port &port)
{
   string reply = aml_read(port);

   cerr << __PRETTY_FUNCTION__ << " reply = " << escape_chars(reply) << endl;
}

#if 0
void aml_wait_for_move_finished(asio::serial_port &port)
{
   size_t loops(0);
   bool move_reply_pending(true);
   bool v_reply_pending(false);

   size_t v_requests_sent(0);
   size_t v_replies_received(0);

   while (move_reply_pending) {
      ++loops;

      if (!v_reply_pending) {
         aml_write(port, "V4\r");
         v_reply_pending = true;
         ++v_requests_sent;
      }

      string reply;

      do {
         reply = aml_read(port);
      } while (!reply.size());

      cerr << __PRETTY_FUNCTION__ << " reply = " << escape_chars(reply) << endl;

      switch (reply.at(0)) {
         case 'B':
            /* Busy reply in response to Vx. Continue polling */
            v_reply_pending = false;
            ++v_replies_received;
            continue;

         case 'V':
            /* Positive response to Vx. Machine is not busy anymore. Stop
             * polling. */
            v_reply_pending = false;
            ++v_replies_received;
            break;

         case 'Y': case 'E':
            move_reply_pending = false;
            break;

         default:
            BOOST_THROW_EXCEPTION(runtime_error()
                  << errinfo_message("unexpected reply: " + escape_chars(reply)));
      }
   }

   cerr << __PRETTY_FUNCTION__ << " v_requests_sent=" << v_requests_sent
      << ", v_replies_received=" << v_replies_received << endl;

   if (v_reply_pending) {
      cerr << __PRETTY_FUNCTION__ << " final V reply read..." << endl;
      string reply(aml_read(port));
      cerr << __PRETTY_FUNCTION__  << " " << escape_chars(reply) << endl;
   }
}
#endif

void do_aml_stuff(asio::serial_port &port)
{
   port.set_option(sp::baud_rate(19200));
   port.set_option(sp::character_size(7));
   port.set_option(sp::parity(sp::parity::odd));
   port.set_option(sp::stop_bits(sp::stop_bits::two));
   port.set_option(sp::flow_control(sp::flow_control::none));

#if 0
   struct termios tio;
   sp::native_handle_type fd(port.native_handle());

   if (tcgetattr(fd, &tio) < 0) throw 42;
   tio.c_cc[VMIN]  = 1;
   tio.c_cc[VTIME] = 5;
   if (tcflush(fd, TCIOFLUSH) < 0 || tcsetattr(fd, TCSANOW, &tio) < 0) throw 42;
#endif

   aml_write(port, "V4\r");
   cout << "initial V4 reply = " << escape_chars(aml_read(port)) << endl;

   aml_write(port, "V1\r");
   cout << "V1 reply = " << escape_chars(aml_read(port)) << endl;

   aml_write(port, "Q\r");

   while (true) {
      string reply = aml_read(port);
      cout << "Q reply: " << escape_chars(reply) << endl;
      if (reply == "Y") break;
   }

   aml_write(port, "V3\r");
   cout << "V3 reply = " << escape_chars(aml_read(port)) << endl;

#if 0
   aml_write(port, "X100,100,10\r");
   cout << "X reply = " << escape_chars(aml_read(port)) << endl;

   int dir = 1;

   for (size_t i=0; i<100; ++i) {
      aml_move_relative(port, 1, 400 * dir);
      aml_wait_for_move_finished(port);

      dir *= -1;
   }
#endif
}

int main(int argc, char *argv[])
{
   po::options_description option_desc("Options");
   option_desc.add_options()
      ("help,h", "show help")
      ("device,D", po::value<string>()->default_value("/dev/ttyUSB0"),  "serial device to use")
      ("type,t",   po::value<string>()->default_value("mrc1")->required(), "device type; one of (mrc1,aml)")
      ;

   po::variables_map options;
   po::store(po::parse_command_line(argc, argv, option_desc), options);
   po::notify(options);

   if (options.count("help")) {
      cout << option_desc << endl;
      return 0;
   }

   string device_name(options["device"].as<string>());
   string device_type(options["type"].as<string>());

   asio::io_service io_service;
   asio::serial_port port(io_service, device_name);

   if (device_type == "mrc1") {
      do_mrc1_stuff(port);
   } else if (device_type == "aml") {
      do_aml_stuff(port);
   } else {
      cout << "Unknown device type " << device_type << endl;
      cout << option_desc << endl;
      return 1;
   }

   cout << boost::format("bytesRead=%1%, bytesWritten=%2%") % g_bytesRead % g_bytesWritten << endl;
}
