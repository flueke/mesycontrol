#ifndef UUID_520d7afb_0f07_4e30_b766_561a3671ca6f
#define UUID_520d7afb_0f07_4e30_b766_561a3671ca6f

#include <boost/asio.hpp>
#include <boost/bind.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/function.hpp>
#include <boost/noncopyable.hpp>
#include <string>

namespace mesycontrol
{

namespace asio = boost::asio;

class MRCComm:
  public boost::enable_shared_from_this<MRCComm>,
  private boost::noncopyable
{
  public:
    typedef boost::function<void (boost::system::error_code, std::size_t)> WriteHandler;
    typedef boost::function<void (boost::system::error_code, std::string)> ReadHandler;

    void write(const std::string &data, WriteHandler handler);
    void read(ReadHandler handler);

    virtual ~MRCComm() {}

  protected:
    typedef boost::function<void (boost::system::error_code, std::size_t)> AsioReadHandler;

    MRCComm(boost::asio::io_service &io,
        const boost::posix_time::time_duration &write_timeout = boost::posix_time::milliseconds(100),
        const boost::posix_time::time_duration &read_timeout  = boost::posix_time::milliseconds(100))
      : m_io(io)
      , m_write_timeout(write_timeout)
      , m_read_timeout(read_timeout)
      , m_busy(false)
      , m_timer(io)
    {}

    virtual void start_write_one(const std::string::const_iterator &it, WriteHandler write_handler) = 0;
    virtual void start_read_one(char &dest, AsioReadHandler read_handler) = 0;
    virtual void cancel_io() = 0;

  private:
    void handle_timeout(const boost::system::error_code &ec);

    void start_write(const std::string::const_iterator &it);
    void handle_write(std::string::const_iterator it, const boost::system::error_code &ec, std::size_t sz);
    void finish_write(std::string::const_iterator it, const boost::system::error_code &ec);

    void start_read();
    void handle_read(const boost::system::error_code &ec, std::size_t sz);
    void finish_read(const boost::system::error_code &ec);


    boost::asio::io_service &m_io;
    boost::posix_time::time_duration m_write_timeout;
    boost::posix_time::time_duration m_read_timeout;
    bool m_busy;
    boost::asio::deadline_timer m_timer;
    std::string m_buf;
    char m_char_buf;
    WriteHandler m_write_handler;
    ReadHandler  m_read_handler;
};

class MRCSerialComm: public MRCComm
{
  public:
    MRCSerialComm(asio::serial_port &port)
      : MRCComm(port.get_io_service())
      , m_port(port)
    {}

  protected:
    virtual void start_write_one(const std::string::const_iterator &it, WriteHandler write_handler)
    {
      asio::async_write(m_port, asio::buffer(&(*it), sizeof(*it)), write_handler);
    }

    virtual void start_read_one(char &dest, AsioReadHandler read_handler)
    {
      asio::async_read(m_port, asio::buffer(&dest, sizeof(dest)), read_handler);
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
    virtual void start_write_one(const std::string::const_iterator &it, WriteHandler write_handler)
    {
      asio::async_write(m_socket, asio::buffer(&(*it), sizeof(*it)), write_handler);
    }

    virtual void start_read_one(char &dest, AsioReadHandler read_handler)
    {
      asio::async_read(m_socket, asio::buffer(&dest, sizeof(dest)), read_handler);
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
