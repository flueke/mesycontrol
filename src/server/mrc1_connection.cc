#include "mrc1_connection.h"
#include "util.h"
#include "protocol.h"

#include <boost/algorithm/string.hpp>
#include <boost/assign/list_of.hpp>
#include <boost/bind.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/foreach.hpp>
#include <boost/format.hpp>
#include <boost/log/trivial.hpp>
#include <boost/make_shared.hpp>
#include <boost/ref.hpp>

namespace asio = boost::asio;
namespace errc = boost::system::errc;

namespace
{
  // source: http://stackoverflow.com/a/2417770
  struct character_escaper
  {
    template<typename FindResultT>
      std::string operator()(const FindResultT& Match) const
      {
        std::string s;
        for (typename FindResultT::const_iterator i = Match.begin();
            i != Match.end();
            ++i) {
          s += str(boost::format("\\x%02x") % static_cast<int>(*i));
        }
        return s;
      }
  };
}

namespace mesycontrol
{

class MRC1Initializer:
  public boost::enable_shared_from_this<MRC1Initializer>,
  private boost::noncopyable
{
  public:
    MRC1Initializer(
        const boost::shared_ptr<MRC1Connection> &mrc1_connection,
        MRC1Connection::ErrorCodeCallback completion_handler):
      m_mrc1(mrc1_connection),
      m_completion_handler(completion_handler),
      m_log(log::keywords::channel="MRC1Initializer")
    {
    }

    void start()
    {
      m_init_data.push_back("\r");   // get rid of any partial data in the MRC buffer
      m_init_data.push_back("p1\r"); // enable mrc prompt
      m_init_data.push_back("x0\r"); // disable mrc echo
      m_init_data.push_back("\r");   // send invalid request which results in error output

      start_write();
    }

  private:
    void start_write()
    {
      m_mrc1->start_write(m_init_data.front(),
          boost::bind(&MRC1Initializer::handle_write, shared_from_this(), _1, _2));
    }

    void handle_write(const boost::system::error_code ec, std::size_t)
    {
      if (!ec) {
        m_mrc1->start_read(
            boost::bind(&MRC1Initializer::handle_read, shared_from_this(), _1, _2));

        m_init_data.pop_front();
      } else {
        BOOST_LOG_SEV(m_log, log::lvl::info) << "init data write error. message:   " << ec.message();
        BOOST_LOG_SEV(m_log, log::lvl::info) << "init data write error. condition: " << ec.default_error_condition().message();

        /* Translate operation_canceled from the timeout handler to a timed_out error. */
        if (ec == errc::operation_canceled)
          m_completion_handler(boost::system::error_code(errc::timed_out, boost::system::system_category()), {});
        else
          m_completion_handler(ec, {});
      }
    }

    void handle_read(const boost::system::error_code ec, std::string data)
    {
      /* operation_canceled means the read timeout expired. This happens if
       * prompt and echo where already disabled. */
      if (!ec || ec == errc::operation_canceled) {

        std::ostream os(&m_read_buffer);
        os << data;

        if (!m_init_data.empty())
          start_write();  // next line of init data
        else
          check_result(); // done
      } else {
        BOOST_LOG_SEV(m_log, log::lvl::info) << "init data read error. message:   " << ec.message();
        BOOST_LOG_SEV(m_log, log::lvl::info) << "init data read error. condition: " << ec.default_error_condition().message();
        m_completion_handler(ec, {});
      }
    }

    void check_result()
    {
      std::istream is(&m_read_buffer);
      std::string line, last_line;

      while (std::getline(is, line)) {
        last_line = line;
        if (is.peek() == '\r')
          is.ignore(1);
      }

      //if (last_line == "ERROR!") {
      if (regex_match(last_line, prompt_regex)) {
        // init success
        m_completion_handler(boost::system::error_code(), {});
      } else {
        std::string last_line_escaped(last_line);
        boost::find_format_all(last_line_escaped, boost::token_finder(!boost::is_print()), character_escaper());
        BOOST_LOG_SEV(m_log, log::lvl::error) << "init failed, last mrc output: " << last_line_escaped;
        // signal failure using a boost system error_code
        m_completion_handler(boost::system::error_code(errc::io_error, boost::system::system_category()), {});
      }
    }

    boost::shared_ptr<MRC1Connection> m_mrc1;
    MRC1Connection::ErrorCodeCallback m_completion_handler;
    boost::asio::streambuf m_read_buffer;
    std::deque<std::string> m_init_data;
    log::Logger m_log;
};

const boost::posix_time::time_duration
MRC1Connection::default_io_timeout(boost::posix_time::milliseconds(100));

const boost::posix_time::time_duration
MRC1Connection::default_reconnect_timeout(boost::posix_time::milliseconds(2500));

const std::string MRC1Connection::response_line_terminator = "\n\r";
const char MRC1Connection::command_terminator = '\r';

MRC1Connection::MRC1Connection(boost::asio::io_context &io_context):
  m_io_context(io_context),
  m_timeout_timer(io_context),
  m_io_timeout(default_io_timeout),
  m_reconnect_timeout(default_reconnect_timeout),
  m_status(proto::MRCStatus::STOPPED),
  m_silenced(false),
  m_auto_reconnect(true),
  m_log(log::keywords::channel="MRC1Connection")
{
}

bool MRC1Connection::is_stopped() const
{
  return m_status == proto::MRCStatus::STOPPED ||
    m_status == proto::MRCStatus::CONNECT_FAILED ||
    m_status == proto::MRCStatus::INIT_FAILED;
}

void MRC1Connection::start()
{
  if (!is_stopped())
    return;

  set_status(proto::MRCStatus::CONNECTING);
  m_last_error = boost::system::error_code();
  m_current_command.reset();
  m_current_response_handler = 0;
  set_silenced(false);

  start_impl(boost::bind(&MRC1Connection::handle_start, shared_from_this(), _1, _2));
}

void MRC1Connection::handle_start(const boost::system::error_code &ec, const std::string &msg)
{
  if (!ec) {
    set_status(proto::MRCStatus::INITIALIZING);
    BOOST_LOG_SEV(m_log, log::lvl::info) << "Initializing MRC";
    boost::make_shared<MRC1Initializer>(shared_from_this(),
        boost::bind(&MRC1Connection::handle_init, shared_from_this(), _1))
      ->start();
  } else {
    stop(ec, proto::MRCStatus::CONNECT_FAILED, msg);
    reconnect_if_enabled();
  }
}

void MRC1Connection::stop()
{
  stop(boost::system::error_code(), proto::MRCStatus::STOPPED);
}

void MRC1Connection::stop(
    const boost::system::error_code &reason,
    proto::MRCStatus::StatusCode new_status,
    const std::string &msg)
{
  stop_impl();
  m_timeout_timer.cancel();
  m_last_error = reason;
  set_status(new_status, reason, {}, false, msg);
  BOOST_LOG_SEV(m_log, log::lvl::info) << "stopped (msg=" << msg << ")";
}

void MRC1Connection::reconnect_if_enabled()
{
  if (get_auto_reconnect()) {
      BOOST_LOG_SEV(m_log, log::lvl::info) << "Reconnecting...";
      m_timeout_timer.expires_from_now(get_reconnect_timeout());
      m_timeout_timer.async_wait(boost::bind(&MRC1Connection::handle_reconnect_timeout, shared_from_this(), _1));
  }
}

void MRC1Connection::handle_init(const boost::system::error_code &ec)
{
  BOOST_LOG_SEV(m_log, log::lvl::info)
    << "MRC1Connection::handle_init: ec=" << ec.message();

  if (!ec) {
    set_status(proto::MRCStatus::RUNNING);
    BOOST_LOG_SEV(m_log, log::lvl::info) << "MRC connection ready";
  } else {
    BOOST_LOG_SEV(m_log, log::lvl::info) << "MRC initialization failed: " << ec.message();
    stop(ec, proto::MRCStatus::INIT_FAILED);
    reconnect_if_enabled();
  }
}

bool MRC1Connection::write_command(const MessagePtr &command,
    ResponseHandler response_handler)
{
  if (!is_running()) {
    BOOST_LOG_SEV(m_log, log::lvl::warning) << "write_command(): service not running";
    return false;
  }

  if (command_in_progress()) {
    BOOST_LOG_SEV(m_log, log::lvl::warning) << "write_command(): another command is in progress";
    return false;
  }

  if (is_silenced()) {
    m_io_context.post(boost::bind(response_handler, command,
          MessageFactory::make_error_response(proto::ResponseError::SILENCED)));
    return true;
  }

  m_current_response_handler = response_handler;
  m_current_command          = command;
  std::string command_string = get_mrc1_command_string(command);
  m_write_buffer             = command_string + command_terminator;
  m_reply_parser.set_current_request(command);

  BOOST_LOG_SEV(m_log, log::lvl::trace)
    << "writing '" << get_mrc1_command_string(command) << "'";

  start_write(m_write_buffer,
      boost::bind(&MRC1Connection::handle_write_command, shared_from_this(), _1, _2));

  return true;
}

void MRC1Connection::handle_write_command(const boost::system::error_code &ec, std::size_t)
{
  if (!is_running()) return;

  if (!ec) {
    m_comm->read_until_prompt(
        boost::bind(&MRC1Connection::handle_command_response_read,
          shared_from_this(), _1, _2));

  } else {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "write failed: " << ec.message();

    MessagePtr response = MessageFactory::make_error_response(
        ec == errc::operation_canceled
        ? proto::ResponseError::COM_TIMEOUT
        : proto::ResponseError::COM_ERROR);
    response->mutable_mrc_status()->set_info(ec.message());

    m_io_context.post(boost::bind(m_current_response_handler, m_current_command, response));
    m_current_command.reset();
    m_current_response_handler = 0;
    stop(ec);
    reconnect_if_enabled();
  }
}

void MRC1Connection::handle_command_response_read(const boost::system::error_code &ec, const std::string &data)
{
  if (!is_running())
    return;

  if (!ec) {
    m_timeout_timer.cancel();
    
    BOOST_LOG_SEV(m_log, log::lvl::trace) << "received line '" << data << "'";

    // FIXME: data might contain the mrc-1> prompt at the very end
    // huh?

    std::vector<std::string> lines;

    boost::split(lines, data, boost::is_any_of("\r\n"), boost::token_compress_on);

    BOOST_LOG_SEV(m_log, log::lvl::trace) << "got " << lines.size() << " lines after split";

    std::for_each(std::begin(lines), std::end(lines), [](std::string &line) { boost::trim(line); });

    lines.erase(std::remove_if(std::begin(lines), std::end(lines),
          [this](const std::string &str) { return str.empty(); }),
        std::end(lines));

    BOOST_LOG_SEV(m_log, log::lvl::trace) << "got " << lines.size() << " lines after trim and erase empty";

#if 0
    for (std::vector<std::string>::const_iterator it=lines.begin();
        it!=lines.end(); ++it) {
      std::string line_escaped(*it);
      boost::find_format_all(line_escaped, boost::token_finder(!boost::is_print()), character_escaper());
      BOOST_LOG_SEV(m_log, log::lvl::debug)
        << "trimmed  line (escaped): '" << line_escaped
        << "', empty(line_escaped)=" << line_escaped.empty()
        << ", empty(*it)=" << it->empty();
    }
#endif

    for (std::vector<std::string>::const_iterator it=lines.begin();
        it!=lines.end(); ++it) {

      std::string line(*it);

      BOOST_LOG_SEV(m_log, log::lvl::debug) << "reply parser got " << line;

      if (!m_reply_parser.parse_line(line)) {
        /* More input needed. */
        BOOST_LOG_SEV(m_log, log::lvl::trace) << "Reply parser needs more input";
        continue;
      } else {
        BOOST_LOG_SEV(m_log, log::lvl::debug) << "reply parsing done, result="
          << proto::Message::Type_Name(m_reply_parser.get_response_message()->type());

        /* Parsing complete. Call the response handler. */
        m_io_context.post(boost::bind(m_current_response_handler, m_current_command,
              m_reply_parser.get_response_message()));

        m_current_command.reset();
        m_current_response_handler = 0;
        break;
      }
    }
  } else {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "read failed: " << ec.message();

    MessagePtr response = MessageFactory::make_error_response(
        ec == errc::operation_canceled ? proto::ResponseError::COM_TIMEOUT : proto::ResponseError::COM_ERROR);
    response->mutable_mrc_status()->set_info(ec.message());

    m_io_context.post(boost::bind(m_current_response_handler, m_current_command, response));
    m_current_command.reset();
    m_current_response_handler = 0;
    stop(ec);
    reconnect_if_enabled();
  }
}

void MRC1Connection::start_write(
    const std::string &data, 
    ReadWriteCallback completion_handler)
{
  if (is_running() || is_initializing()) {
    m_comm->write(data, completion_handler);
  }
}

void MRC1Connection::start_read(MRCComm::ReadHandler read_handler)
{
  m_comm->read(read_handler);
}

void MRC1Connection::handle_io_timeout(const boost::system::error_code &ec)
{
  if (!is_running() && !is_initializing())
    return;

  /* Make sure the deadline has passed. Another asynchronous operation may have
   * moved the deadline before this actor had a chance to run. */
  if (ec != boost::asio::error::operation_aborted &&
      m_timeout_timer.expires_at() <= boost::asio::deadline_timer::traits_type::now()) {
    cancel_io();
  }
}

void MRC1Connection::handle_reconnect_timeout(const boost::system::error_code &ec)
{
  if (ec != boost::asio::error::operation_aborted &&
      m_timeout_timer.expires_at() <= boost::asio::deadline_timer::traits_type::now()) {
    start();
  }
}

void MRC1Connection::set_status(
    const proto::MRCStatus::StatusCode &status,
    const boost::system::error_code &reason,
    const std::string &version,
    bool has_read_multi,
    const std::string &msg)
{
  BOOST_LOG_SEV(m_log, log::lvl::info) << "MRC status changed: "
    << proto::MRCStatus::StatusCode_Name(m_status)
    << " -> "
    << proto::MRCStatus::StatusCode_Name(status)
    << "(reason="  << reason.value()
    << ",info=\""  << reason.message()
    << "\",version="  << version
    << ",has_read_multi=" << has_read_multi
    << ", msg=\"" << msg << "\""
    << ")";

  m_status = status;

  BOOST_FOREACH(StatusChangeCallback callback, m_status_change_callbacks) {
    callback(m_status, reason, version, has_read_multi, msg);
  }
}

void MRC1Connection::register_status_change_callback(const StatusChangeCallback &callback)
{
  m_status_change_callbacks.push_back(callback);
}

const std::vector<unsigned int> MRC1SerialConnection::default_baud_rates =
  boost::assign::list_of(115200)(9600)(19200)(38400)(57600);

MRC1SerialConnection::MRC1SerialConnection(boost::asio::io_context &io_context,
    const std::string &serial_device, unsigned int baud_rate):
  MRC1Connection(io_context),
  m_serial_device(serial_device),
  m_requested_baud_rate(baud_rate),
  m_current_baud_rate_idx(0),
  m_port(io_context)
{
  set_comm(boost::make_shared<MRCSerialComm>(boost::ref(m_port), boost::ref(io_context)));
}

void MRC1SerialConnection::start_impl(ErrorCodeCallback completion_handler)
{
  try {
    unsigned int baud_rate = get_baud_rate();
    BOOST_LOG_SEV(m_log, log::lvl::info) << "Opening " << m_serial_device << ", baud_rate=" << baud_rate;
    m_port.open(m_serial_device);

#ifndef BOOST_WINDOWS
    if (ioctl(m_port.native_handle(), TIOCEXCL) < 0) {
      BOOST_THROW_EXCEPTION(boost::system::system_error(
            errno, boost::system::system_category(), "ioctl"));
    }
#endif

    m_port.set_option(asio::serial_port::baud_rate(baud_rate));
    m_port.set_option(asio::serial_port::character_size(8));
    m_port.set_option(asio::serial_port::parity(asio::serial_port::parity::none));
    m_port.set_option(asio::serial_port::stop_bits(asio::serial_port::stop_bits::one));
    m_port.set_option(asio::serial_port::flow_control(asio::serial_port::flow_control::none));

#ifndef BOOST_WINDOWS
    if (tcflush(m_port.native_handle(), TCIOFLUSH) < 0) {
        BOOST_THROW_EXCEPTION(boost::system::system_error(
                    errno, boost::system::system_category(), "tcflush"));
    }
#endif

    completion_handler(boost::system::error_code(), {});
  } catch (const boost::system::system_error &e) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "Failed opening " << m_serial_device
      << ": " << e.what();
    completion_handler(e.code(), {});
  }
}

void MRC1SerialConnection::stop_impl()
{
  boost::system::error_code ignored_ec;
  m_port.close(ignored_ec);
}

void MRC1SerialConnection::cancel_io()
{
  boost::system::error_code ignored_ec;
  m_port.cancel(ignored_ec);
}

void MRC1SerialConnection::handle_init(
    const boost::system::error_code &ec)
{
  if (ec) {
    set_next_baud_rate();
  }
  MRC1Connection::handle_init(ec);
}

unsigned int MRC1SerialConnection::get_baud_rate()
{
  if (m_requested_baud_rate != 0)
    return m_requested_baud_rate;
  return default_baud_rates[m_current_baud_rate_idx];
}

void MRC1SerialConnection::set_next_baud_rate()
{
  m_current_baud_rate_idx += 1;
  m_current_baud_rate_idx %= default_baud_rates.size();

  BOOST_LOG_SEV(m_log, log::lvl::info)
    << "MRC1SerialConnection: next baud rate setting is " << get_baud_rate();
}

MRC1TCPConnection::MRC1TCPConnection(boost::asio::io_context &io_context,
    const std::string &host, unsigned short port):
  MRC1Connection(io_context),
  m_host(host),
  m_service(boost::lexical_cast<std::string>(port)),
  m_socket(io_context),
  m_resolver(io_context)
{
  set_comm(boost::make_shared<MRCTCPComm>(boost::ref(m_socket), boost::ref(io_context)));
}

MRC1TCPConnection::MRC1TCPConnection(boost::asio::io_context &io_context,
    const std::string &host, const std::string &service):
  MRC1Connection(io_context),
  m_host(host),
  m_service(service),
  m_socket(io_context),
  m_resolver(io_context)
{
  set_comm(boost::make_shared<MRCTCPComm>(boost::ref(m_socket), boost::ref(io_context)));
}

void MRC1TCPConnection::start_impl(ErrorCodeCallback completion_handler)
{
  /* Perform resolve and connect synchronously to work around
   * https://svn.boost.org/trac/boost/ticket/8795 */
  try {
    using boost::asio::ip::tcp;
    BOOST_LOG_SEV(m_log, log::lvl::info) << "Connecting to "
      << m_host << ":" << m_service;

    tcp::resolver::query query(m_host, m_service);
    tcp::resolver::iterator endpoint_iter(m_resolver.resolve(query));
    asio::connect(m_socket, endpoint_iter);
    m_socket.set_option(asio::ip::tcp::no_delay(true));

    completion_handler(boost::system::error_code(), {});
  } catch (const boost::system::system_error &e) {
    BOOST_LOG_SEV(m_log, log::lvl::error) << "Could not connect to "
      << m_host << ":" << m_service
      << ": " << e.what();


    // TODO: pass more info in the error messages info string, e.g.:
    std::ostringstream ss;
    ss << "Could not connect to " << m_host << ": " << e.what();
    completion_handler(e.code(), ss.str());
    
    //completion_handler(e.code());
  }
}

void MRC1TCPConnection::stop_impl()
{
  boost::system::error_code ignored_ec;
  m_socket.close(ignored_ec);
}

void MRC1TCPConnection::cancel_io()
{
  boost::system::error_code ignored_ec;
  m_socket.cancel(ignored_ec);
}

} // namespace mesycontrol
