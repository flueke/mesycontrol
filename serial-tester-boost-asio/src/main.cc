#include <boost/asio.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include <boost/exception/all.hpp>
#include <boost/function.hpp>
#include <boost/make_shared.hpp>
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
namespace asio = boost::asio;

typedef asio::serial_port sp;

typedef boost::function<void (boost::system::error_code, std::size_t)> WriteHandler;
typedef boost::function<void (boost::system::error_code, std::string)> ReadHandler;

class Serial:
  public boost::enable_shared_from_this<Serial>,
  private boost::noncopyable
{
  public:
    Serial(sp &port)
      : m_port(port)
      , m_write_timeout_ms(boost::posix_time::milliseconds(100))
      , m_read_timeout_ms(boost::posix_time::milliseconds(100))
      , m_busy(false)
      , m_timer(m_port.get_io_service())
    {}

    void write(const std::string &data, WriteHandler handler)
    {
      // Write one char from the given data string at a time using a timeout of
      // m_write_timeout_ms.
      // If all characters have been written or a timeout occured call the given WriteHandler
      
      if (m_busy)
        throw std::runtime_error("Serial port is busy");

      m_busy = true;
      m_buf  = data;
      m_write_handler = handler;
      start_write(m_buf.begin());
    }

    void read(ReadHandler handler)
    {
      // Read until a timeout or an error occurs.
      // Call the given ReadHandler with an appropriate error code and the read
      // data.

      if (m_busy)
        throw std::runtime_error("Serial port is busy");

      m_busy = true;
      m_buf.clear();
      m_read_handler = handler;
      start_read();
    }

  private:
    void handle_timeout(const boost::system::error_code &ec)
    {
      if (ec != asio::error::operation_aborted &&
          m_timer.expires_at() <= asio::deadline_timer::traits_type::now()) {
        m_port.cancel();
      }
    }

    void start_write(std::string::const_iterator it)
    {
      if (it == m_buf.end()) {
        finish_write(it, boost::system::error_code());
      } else {
        m_timer.expires_from_now(m_write_timeout_ms);
        m_timer.async_wait(boost::bind(&Serial::handle_timeout, shared_from_this(), _1));
        asio::async_write(m_port, asio::buffer(&(*it), sizeof(*it)),
            boost::bind(&Serial::handle_write, shared_from_this(), it, _1, _2));
      }
    }

    void handle_write(std::string::const_iterator it, const boost::system::error_code &ec, std::size_t sz)
    {
      if (!ec) {
        m_timer.cancel();
        start_write(++it);
      } else {
        finish_write(it, ec);
      }
    }

    void finish_write(std::string::const_iterator it, const boost::system::error_code &ec)
    {
      m_timer.cancel();
      m_port.get_io_service().post(boost::bind(m_write_handler, ec, it - m_buf.begin()));
      m_busy = false;
      m_write_handler = 0;
      m_buf.clear();
    }

    void start_read()
    {
      m_timer.expires_from_now(m_read_timeout_ms);
      m_timer.async_wait(boost::bind(&Serial::handle_timeout, shared_from_this(), _1));
      asio::async_read(m_port, asio::buffer(&m_char_buf, sizeof(m_char_buf)),
          boost::bind(&Serial::handle_read, shared_from_this(), _1, _2));
    }

    void handle_read(const boost::system::error_code &ec, std::size_t sz)
    {
      if (!ec) {
        m_timer.cancel();
        m_buf.push_back(m_char_buf);
        start_read();
      } else {
        finish_read(ec);
      }
    }

    void finish_read(const boost::system::error_code &ec)
    {
      m_timer.cancel();
      m_port.get_io_service().post(boost::bind(m_read_handler, ec, m_buf));
      m_busy = false;
      m_read_handler = 0;
      m_buf.clear();
    }

    sp &m_port;
    boost::posix_time::time_duration m_write_timeout_ms;
    boost::posix_time::time_duration m_read_timeout_ms;
    bool m_busy;
    asio::deadline_timer m_timer;
    std::string m_buf;
    char m_char_buf;
    WriteHandler m_write_handler;
    ReadHandler  m_read_handler;
};

void handle_read(Serial *serial, boost::system::error_code ec, std::string data)
{
  cout << "handle_read: " << data << "(" << data.size() << ")" << endl;
}

void handle_write(boost::system::error_code ec, std::size_t sz)
{
  cout << "handle_write" << ec << sz << endl;
}


int main(int argc, char *argv[])
{
  asio::io_service io;
  sp port(io);
  port.open("/dev/ttyUSB0");
  port.set_option(sp::baud_rate(115200));

  boost::shared_ptr<Serial> serial(boost::make_shared<Serial>(port));

  boost::function<void (Serial *, boost::system::error_code, std::string)> read_handler(
      boost::bind(handle_read, serial.get(), _2, _3));

  io.post(boost::bind(&Serial::read, serial, read_handler));
  io.run();
}
