#ifndef UUID_520d7afb_0f07_4e30_b766_561a3671ca6f
#define UUID_520d7afb_0f07_4e30_b766_561a3671ca6f

#include <boost/asio.hpp>
#include <boost/bind.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/function.hpp>
#include <boost/noncopyable.hpp>
#include <boost/regex.hpp>
#include <string>
#include "logging.h"

namespace mesycontrol
{

namespace asio = boost::asio;
namespace pt   = boost::posix_time;

static const std::string prompt_pattern = "^mrc-1>";
static const boost::regex prompt_regex("^mrc-1>");

static const pt::time_duration default_read_timeout  = pt::milliseconds(100);
static const pt::time_duration default_write_timeout = pt::milliseconds(100);

static const pt::time_duration default_serial_read_timeout  = pt::milliseconds(50);
static const pt::time_duration default_serial_write_timeout = pt::milliseconds(500);

static const pt::time_duration default_read_until_prompt_timeout = pt::milliseconds(500);

class MRCComm:
  public boost::enable_shared_from_this<MRCComm>,
  private boost::noncopyable
{
  public:
    typedef boost::function<void (boost::system::error_code, std::size_t)> WriteHandler;
    typedef boost::function<void (boost::system::error_code, std::string)> ReadHandler;

    void write(const std::string &data, WriteHandler handler);
    void read(ReadHandler handler);
    void read_until_prompt(ReadHandler handler);

    virtual ~MRCComm() {}

  protected:
    typedef boost::function<void (boost::system::error_code, std::size_t)> AsioReadHandler;

    MRCComm(asio::io_service &io,
        const pt::time_duration &read_timeout  = default_read_timeout,
        const pt::time_duration &write_timeout = default_write_timeout)
      : m_io(io)
      , m_read_timeout(read_timeout)
      , m_write_timeout(write_timeout)
      , m_busy(false)
      , m_timer(io)
    {}

    virtual void start_write_one(const std::string::const_iterator it,
        WriteHandler write_handler) = 0;

    virtual void start_read_one(char &dest, AsioReadHandler read_handler) = 0;

    virtual void start_read_until_prompt(asio::streambuf &read_buffer,
        AsioReadHandler read_handler) = 0;

    virtual void cancel_io() = 0;

    log::Logger m_log;

  private:
    void handle_timeout(boost::system::error_code ec);

    void start_write(const std::string::const_iterator &it);
    void handle_write(std::string::const_iterator it, boost::system::error_code ec, std::size_t sz);
    void finish_write(std::string::const_iterator it, boost::system::error_code ec);

    void start_read();
    void handle_read(const boost::system::error_code &ec, std::size_t sz);
    void finish_read(const boost::system::error_code &ec);

    void finish_read_until_prompt(const boost::system::error_code &ec, std::size_t sz);
    void handle_read_until_prompt_timeout(boost::system::error_code ec);


    asio::io_service &m_io;
    pt::time_duration m_read_timeout;
    pt::time_duration m_write_timeout;
    bool m_busy;
    asio::deadline_timer m_timer;
    std::string m_str_buf;
    char m_char_buf;
    asio::streambuf m_asio_buf;
    ReadHandler  m_read_handler;
    WriteHandler m_write_handler;
};

class MRCSerialComm: public MRCComm
{
  public:
    MRCSerialComm(asio::serial_port &port)
      : MRCComm(port.get_io_service()
          , default_serial_read_timeout
          , default_serial_write_timeout
          )
      , m_port(port)
    {}

  protected:
    virtual void start_write_one(const std::string::const_iterator it, WriteHandler write_handler)
    {
      asio::async_write(m_port, asio::buffer(&(*it), sizeof(*it)), write_handler);
    }

    virtual void start_read_one(char &dest, AsioReadHandler read_handler)
    {
      asio::async_read(m_port, asio::buffer(&dest, sizeof(dest)), read_handler);
    }

    virtual void start_read_until_prompt(asio::streambuf &read_buffer,
        AsioReadHandler read_handler)
    {
      asio::async_read_until(m_port, read_buffer, prompt_regex, read_handler);
    }

    virtual void cancel_io()
    {
      m_port.cancel();
    }

  private:
    asio::serial_port &m_port;
};

class MRCTCPComm: public MRCComm
{
  public:
    MRCTCPComm(asio::ip::tcp::socket &socket)
      : MRCComm(socket.get_io_service())
      , m_socket(socket)
    {}

  protected:
    virtual void start_write_one(const std::string::const_iterator it, WriteHandler write_handler)
    {
      asio::async_write(m_socket, asio::buffer(&(*it), sizeof(*it)), write_handler);
    }

    virtual void start_read_one(char &dest, AsioReadHandler read_handler)
    {
      asio::async_read(m_socket, asio::buffer(&dest, sizeof(dest)), read_handler);
    }

    virtual void start_read_until_prompt(asio::streambuf &read_buffer,
        AsioReadHandler read_handler)
    {
      asio::async_read_until(m_socket, read_buffer, prompt_regex, read_handler);
    }

    virtual void cancel_io()
    {
      m_socket.cancel();
    }

  private:
    asio::ip::tcp::socket &m_socket;
};

} // ns mesycontrol

#endif
