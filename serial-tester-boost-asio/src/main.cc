#include <boost/algorithm/string/predicate.hpp>
#include <boost/assign.hpp>
#include <boost/asio.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include <boost/exception/all.hpp>
#include <boost/function.hpp>
#include <boost/make_shared.hpp>
#include <boost/random.hpp>
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

class MRCComm:
  public boost::enable_shared_from_this<MRCComm>,
  private boost::noncopyable
{
  public:
    typedef boost::function<void (boost::system::error_code, std::size_t)> WriteHandler;
    typedef boost::function<void (boost::system::error_code, std::string)> ReadHandler;

    void write(const std::string &data, WriteHandler handler)
    {
      if (m_busy)
        throw std::runtime_error("MRCComm is busy");

      m_busy = true;
      m_buf  = data;
      m_write_handler = handler;
      start_write(m_buf.begin());
    }

    void read(ReadHandler handler)
    {
      if (m_busy)
        throw std::runtime_error("MRCComm is busy");

      m_busy = true;
      m_buf.clear();
      m_read_handler = handler;
      start_read();
    }

    virtual ~MRCComm() {}

  protected:
    MRCComm(boost::asio::io_service &io,
        const boost::posix_time::time_duration &write_timeout = boost::posix_time::milliseconds(100),
        const boost::posix_time::time_duration &read_timeout  = boost::posix_time::milliseconds(100))
      : m_io(io)
      , m_write_timeout(write_timeout)
      , m_read_timeout(read_timeout)
      , m_busy(false)
      , m_timer(io)
    {}

    virtual void start_write_one(const std::string::const_iterator &it,
        boost::function<void (boost::system::error_code, std::size_t)> write_handler) = 0;

    virtual void start_read_one(char &dest,
        boost::function<void (boost::system::error_code, std::size_t)> read_handler) = 0;

    virtual void cancel_io() = 0;

  private:
    void handle_timeout(const boost::system::error_code &ec)
    {
      if (ec != asio::error::operation_aborted &&
          m_timer.expires_at() <= asio::deadline_timer::traits_type::now()) {
        cancel_io();
      }
    }

    void start_write(const std::string::const_iterator &it)
    {
      if (it == m_buf.end()) {
        finish_write(it, boost::system::error_code());
      } else {
        m_timer.expires_from_now(m_write_timeout);
        m_timer.async_wait(boost::bind(&MRCComm::handle_timeout, shared_from_this(), _1));
        start_write_one(it, boost::bind(&MRCComm::handle_write, shared_from_this(), it, _1, _2));
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
      m_io.post(boost::bind(m_write_handler, ec, it - m_buf.begin()));
      m_busy = false;
      m_write_handler = 0;
      m_buf.clear();
    }

    void start_read()
    {
      m_timer.expires_from_now(m_read_timeout);
      m_timer.async_wait(boost::bind(&MRCComm::handle_timeout, shared_from_this(), _1));
      start_read_one(m_char_buf, boost::bind(&MRCComm::handle_read, shared_from_this(), _1, _2));
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
      m_io.post(boost::bind(m_read_handler,
            ec == boost::system::errc::operation_canceled ? boost::system::error_code() : ec,
            m_buf));
      m_busy = false;
      m_read_handler = 0;
      m_buf.clear();
    }

    asio::io_service &m_io;
    boost::posix_time::time_duration m_write_timeout;
    boost::posix_time::time_duration m_read_timeout;
    bool m_busy;
    asio::deadline_timer m_timer;
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
    virtual void start_write_one(const std::string::const_iterator &it,
        boost::function<void (boost::system::error_code, std::size_t)> write_handler)
    {
      asio::async_write(m_port, asio::buffer(&(*it), sizeof(*it)), write_handler);
    }

    virtual void start_read_one(char &dest,
        boost::function<void (boost::system::error_code, std::size_t)> read_handler)
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
    virtual void start_write_one(const std::string::const_iterator &it,
        boost::function<void (boost::system::error_code, std::size_t)> write_handler)
    {
      asio::async_write(m_socket, asio::buffer(&(*it), sizeof(*it)), write_handler);
    }

    virtual void start_read_one(char &dest,
        boost::function<void (boost::system::error_code, std::size_t)> read_handler)
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

void handle_write(const boost::shared_ptr<MRCComm> &mrc, boost::system::error_code ec, std::size_t sz);

void handle_read(const boost::shared_ptr<MRCComm> &mrc, boost::system::error_code ec, std::string data)
{
  cout << "handle_read: " << data << " (" << data.size() << ")"
    << "(" << ec << ", " << ec.message() << ")" << endl;

  if (ec) {
    throw std::runtime_error("read failed");
  }

  if (data.size() && !boost::algorithm::ends_with(data, "mrc-1>")) {
    throw std::runtime_error("Could not find prompt in MRC response");
  }

  static std::vector<std::string> commands = boost::assign::list_of
    ("?")("SC 0")("SC 1")("LI")("PS")("garbage")("X0")("X1")("RE 0 1 0");

  static boost::random::mt19937 gen;
  static boost::random::uniform_int_distribution<> dist(0, commands.size()-1);

  const std::string &command(commands[dist(gen)]);

  cout << "Writing '" << command << "'" << endl;

  mrc->write(command + '\r', boost::bind(handle_write, mrc, _1, _2));
}

void handle_write(const boost::shared_ptr<MRCComm> &mrc, boost::system::error_code ec, std::size_t sz)
{
  cout << "handle_write: " << ec << ", " << ec.message() << " (" << sz << ")" << endl;

  if (ec) {
    throw std::runtime_error("write failed");
  }

  mrc->read(boost::bind(handle_read, mrc, _1, _2));
}

int main(int argc, char *argv[])
{
  asio::io_service io;

#if 0
  asio::serial_port port(io);
  port.open("/dev/ttyUSB0");
  port.set_option(asio::serial_port::baud_rate(115200));
  boost::shared_ptr<MRCComm> mrc(boost::make_shared<MRCSerialComm>(port));
#else
  asio::ip::tcp::socket socket(io);
  asio::ip::tcp::resolver resolver(io);
  asio::ip::tcp::resolver::query query("localhost", "4001");
  asio::ip::tcp::resolver::iterator endpoint_iter(resolver.resolve(query));
  asio::connect(socket, endpoint_iter);
  socket.set_option(asio::ip::tcp::no_delay(true));
  boost::shared_ptr<MRCComm> mrc(boost::make_shared<MRCTCPComm>(socket));
#endif

  boost::function<void (boost::system::error_code, std::string)> read_handler(
      boost::bind(handle_read, mrc, _1, _2));

  io.post(boost::bind(&MRCComm::read, mrc, read_handler));
  io.run();
}
