#include <boost/bind.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/make_shared.hpp>
#include "mrc1_connection.h"

namespace asio = boost::asio;
namespace errc = boost::system::errc;

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
      m_completion_handler(completion_handler)
    {
      start();
    }

  private:
    void start()
    {
      m_init_data.push_back("p0\r"); // disable mrc prompt
      m_init_data.push_back("x0\r"); // disable mrc echo
      m_init_data.push_back("\r");   // send invalid request which results in error output

      start_write();
    }

    void start_write()
    {
      m_mrc1->start_write(m_init_data.front(),
          boost::bind(&MRC1Initializer::handle_write, shared_from_this(), _1, _2));
    }

    void handle_write(const boost::system::error_code &ec, std::size_t)
    {
      if (!ec) {
        m_mrc1->start_read(m_read_buffer,
            boost::bind(&MRC1Initializer::handle_read, shared_from_this(), _1, _2));

        m_init_data.pop_front();
      } else {
        /* Translate operation_canceled from the timeout handler to a timed_out error. */
        if (ec == errc::operation_canceled)
          m_completion_handler(boost::system::error_code(errc::timed_out, boost::system::system_category()));
        else
          m_completion_handler(ec);
      }
    }

    void handle_read(const boost::system::error_code &ec, std::size_t bytes)
    {
      /* operation_canceled means the read timeout expired. This happens if
       * prompt and echo where already disabled. */
      if (!ec || ec == errc::operation_canceled) {
        if (!m_init_data.empty())
          start_write();  // next line of init data
        else
          check_result(); // done
      } else {
        m_completion_handler(ec);
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

      if (last_line == "ERROR!") {
        // init success
        m_completion_handler(boost::system::error_code());
      } else {
        // signal failure using io_error for now
        m_completion_handler(boost::system::error_code(errc::io_error, boost::system::system_category())); 
      }
    }

    boost::shared_ptr<MRC1Connection> m_mrc1;
    MRC1Connection::ErrorCodeCallback m_completion_handler;
    boost::asio::streambuf m_read_buffer;
    std::deque<std::string> m_init_data;
};

const int MRC1Connection::default_timeout_ms = 100;
const char *MRC1Connection::response_line_terminator = "\r\n";
const char MRC1Connection::command_terminator = '\r';

MRC1Connection::MRC1Connection(boost::asio::io_service &io_service):
  m_io_service(io_service),
  m_timeout_timer(io_service),
  m_timeout(boost::posix_time::milliseconds(default_timeout_ms)),
  m_status(stopped)
{
}

void MRC1Connection::start()
{
  if (m_status != stopped)
    return;

  m_status = connecting;

  m_timeout_timer.expires_at(boost::posix_time::pos_infin);
  m_timeout_timer.async_wait(boost::bind(&MRC1Connection::handle_timeout, shared_from_this(), _1));

  start_impl(boost::bind(&MRC1Connection::handle_start, shared_from_this(), _1));
}

void MRC1Connection::handle_start(const boost::system::error_code &ec)
{
  if (!ec) {
    m_status = initializing;
    boost::make_shared<MRC1Initializer>(shared_from_this(),
        boost::bind(&MRC1Connection::handle_init, shared_from_this(), _1));
  } else {
    m_status = connect_failed;
    m_last_error = ec;
  }
}

void MRC1Connection::stop()
{
  if (m_status == stopped)
    return;

  stop_impl();
  m_status = stopped;
}

void MRC1Connection::handle_init(const boost::system::error_code &ec)
{
  if (!ec) {
    m_status = running;
  } else {
    m_status = init_failed;
    m_last_error = ec;
  }
}

bool MRC1Connection::write_command(const MessagePtr &command,
    ResponseHandler &response_handler)
{
  if (m_current_command) return false;

  m_current_response_handler = response_handler;
  m_current_command = command;
  m_write_buffer    = command->get_mrc1_command_string() + command_terminator;

  start_write(m_write_buffer,
      boost::bind(&MRC1Connection::handle_write_command, shared_from_this(), _1, _2));

  return true;
}

void MRC1Connection::handle_write_command(const boost::system::error_code &ec, std::size_t)
{
  if (!ec) {
    m_reply_parser.set_current_request(m_current_command);
    start_read_line(m_read_buffer,
      boost::bind(&MRC1Connection::handle_read_line, shared_from_this(), _1, _2));
  } else {
    m_current_response_handler(m_current_command, Message::make_error_response(
          ec == errc::operation_canceled ? error_type::mrc_comm_timeout : error_type::mrc_comm_error));
    m_current_command.reset();
    m_current_response_handler = 0;
  }
}

void MRC1Connection::handle_read_line(const boost::system::error_code &ec, std::size_t)
{
  if (!ec) {
    std::string reply_line;
    std::istream is(&m_read_buffer);
    std::getline(is, reply_line);
    is.ignore(1); // consume the trailing \r

    if (!m_reply_parser.parse_line(reply_line)) {
      /* More input needed. */
      start_read_line(m_read_buffer,
          boost::bind(&MRC1Connection::handle_read_line, shared_from_this(), _1, _2));
    } else {
      /* Parsing complete. Call the response handler. */
      m_current_response_handler(m_current_command, m_reply_parser.get_response_message());
      m_current_command.reset();
      m_current_response_handler = 0;
    }
  } else {
    m_current_response_handler(m_current_command, Message::make_error_response(
          ec == errc::operation_canceled ? error_type::mrc_comm_timeout : error_type::mrc_comm_error));
    m_current_command.reset();
    m_current_response_handler = 0;
  }
}

void MRC1Connection::start_write(
    const std::string &data, 
    ReadWriteCallback completion_handler)
{
  m_timeout_timer.expires_from_now(get_timeout());
  start_write_impl(data, completion_handler);
}

void MRC1Connection::start_read(
    boost::asio::streambuf &read_buffer,
    ReadWriteCallback completion_handler)
{
  m_timeout_timer.expires_from_now(get_timeout());
  start_read_impl(read_buffer, completion_handler);
}

void MRC1Connection::start_read_line(
    boost::asio::streambuf &read_buffer,
    ReadWriteCallback completion_handler)
{
  m_timeout_timer.expires_from_now(get_timeout());
  start_read_line_impl(read_buffer, completion_handler);
}

void MRC1Connection::handle_timeout(const boost::system::error_code &ec)
{
  if (m_timeout_timer.expires_at() <= boost::asio::deadline_timer::traits_type::now()) {
    /* Cancel the ongoing read/write operation. This will result in active
     * read/write handlers being called with errc::operation_canceled. */
    cancel_io();
  }

  /* Rearm the timer with an infinite time. The correct timeout will be set by
   * the start_read/write methods. */
  m_timeout_timer.expires_at(boost::posix_time::pos_infin);
  m_timeout_timer.async_wait(boost::bind(&MRC1Connection::handle_timeout, shared_from_this(), _1));
}

MRC1SerialConnection::MRC1SerialConnection(boost::asio::io_service &io_service,
    const std::string &serial_device, unsigned int baud_rate):
  MRC1Connection(io_service),
  m_serial_device(serial_device),
  m_baud_rate(baud_rate),
  m_port(io_service)
{
}

void MRC1SerialConnection::start_impl(ErrorCodeCallback completion_handler)
{
  try {
    m_port.open(m_serial_device);
    m_port.set_option(asio::serial_port::baud_rate(m_baud_rate));
    m_port.set_option(asio::serial_port::character_size(8));
    m_port.set_option(asio::serial_port::parity(asio::serial_port::parity::none));
    m_port.set_option(asio::serial_port::stop_bits(asio::serial_port::stop_bits::one));
    m_port.set_option(asio::serial_port::flow_control(asio::serial_port::flow_control::none));
    completion_handler(boost::system::error_code());
  } catch (const boost::system::system_error &e) {
    completion_handler(e.code());
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

void MRC1SerialConnection::start_write_impl(
    const std::string &data,
    ReadWriteCallback completion_handler)
{
  asio::async_write(m_port, asio::buffer(data), completion_handler);
}

void MRC1SerialConnection::start_read_impl(
    boost::asio::streambuf &read_buffer,
    ReadWriteCallback completion_handler)
{
  asio::async_read(m_port, read_buffer, completion_handler);
}

void MRC1SerialConnection::start_read_line_impl(
    boost::asio::streambuf &read_buffer,
    ReadWriteCallback completion_handler)
{
  asio::async_read_until(m_port, read_buffer, response_line_terminator,
      completion_handler);
}

MRC1TCPConnection::MRC1TCPConnection(boost::asio::io_service &io_service,
    const std::string &host, unsigned short port):
  MRC1Connection(io_service),
  m_host(host),
  m_service(boost::lexical_cast<std::string>(port)),
  m_socket(io_service),
  m_resolver(io_service)
{
}

MRC1TCPConnection::MRC1TCPConnection(boost::asio::io_service &io_service,
    const std::string &host, const std::string &service):
  MRC1Connection(io_service),
  m_host(host),
  m_service(service),
  m_socket(io_service),
  m_resolver(io_service)
{
}

void MRC1TCPConnection::start_impl(ErrorCodeCallback completion_handler)
{
  /* Perform resolve and connect synchronously to work around
   * https://svn.boost.org/trac/boost/ticket/8795 */
  try {
    using boost::asio::ip::tcp;
    tcp::resolver::query query(m_host, m_service);
    tcp::resolver::iterator endpoint_iter(m_resolver.resolve(query));
    asio::connect(m_socket, endpoint_iter);
    m_socket.set_option(asio::ip::tcp::no_delay(true));
  } catch (const boost::system::system_error &e) {
    completion_handler(e.code());
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

void MRC1TCPConnection::start_write_impl(
    const std::string &data,
    ReadWriteCallback completion_handler)
{
  asio::async_write(m_socket, asio::buffer(data), completion_handler);
}

void MRC1TCPConnection::start_read_impl(
    boost::asio::streambuf &read_buffer,
    ReadWriteCallback completion_handler)
{
  asio::async_read(m_socket, read_buffer, completion_handler);
}

void MRC1TCPConnection::start_read_line_impl(
    boost::asio::streambuf &read_buffer,
    ReadWriteCallback completion_handler)
{
  asio::async_read_until(m_socket, read_buffer, response_line_terminator,
      completion_handler);
}

} // namespace mesycontrol
