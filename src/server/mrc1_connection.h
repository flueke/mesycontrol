#ifndef UUID_017b76b7_0732_40a0_8fd5_a9c9a90700d0
#define UUID_017b76b7_0732_40a0_8fd5_a9c9a90700d0

#include "config.h"
#include <boost/asio.hpp>
#include <boost/date_time/posix_time/posix_time.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/function.hpp>
#include <boost/shared_ptr.hpp>
#include <boost/utility.hpp>
#include <string>
#include "handler_types.h"
#include "mrc1_reply_parser.h"

namespace mesycontrol
{

class MRC1Connection:
  public boost::enable_shared_from_this<MRC1Connection>,
  private boost::noncopyable
{
  public:
    enum Status
    {
      stopped,
      connecting,
      initializing,
      running,
      connect_failed,
      init_failed,
      timed_out
    };

    static const int default_timeout_ms;

    MRC1Connection(boost::asio::io_service &io_service);

    /** Start the connection. Opens the connection and performs the MRC
     * initialization sequence. */
    void start();

    /** Stop the connection. Cancels pending commands and closes the
     * connection. Use start() to start it again. */
    void stop();

    boost::posix_time::time_duration get_timeout() const
    {
      return m_timeout;
    }

    void set_timeout(const boost::posix_time::time_duration &timeout)
    {
      m_timeout = timeout;
    }

    bool write_command(const MessagePtr &command,
        ResponseHandler &response_handler);

    Status get_status() const { return m_status; }
    bool is_initialized() const { return m_status == running; }
    boost::system::error_code get_last_error() const { return m_last_error; }
    void reset_last_error() { m_last_error = boost::system::error_code(); }

    virtual ~MRC1Connection() {};

  protected:
    typedef boost::function<void (const boost::system::error_code &, std::size_t)>
      ReadWriteCallback;

    typedef boost::function<void (const boost::system::error_code &)>
      ErrorCodeCallback;

    /** Start an async write of the given data, using the given completion handler.
     * The caller has to ensure the reference to data remains valid until the
     * write completes so no copy has to be created. */
    void start_write(
        const std::string &data, 
        ReadWriteCallback completion_handler);

    void start_read(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler);

    void start_read_line(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler);

    /** Start implementation. Open files here / resolve hostnames, etc.
     * Call the given completion_handler once startup is complete. */
    virtual void start_impl(ErrorCodeCallback completion_handler) = 0;

    /** Stop implementation. Close files, etc. */
    virtual void stop_impl() = 0;

    /** Cancel pending async IO requests. */
    virtual void cancel_io() = 0;

    virtual void start_write_impl(
        const std::string &data,
        ReadWriteCallback completion_handler) = 0;

    virtual void start_read_impl(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler) = 0;

    virtual void start_read_line_impl(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler) = 0;

    static const char *response_line_terminator;
    static const char command_terminator;

  private:
    void handle_write_command(const boost::system::error_code &ec, std::size_t bytes);
    void handle_read_line(const boost::system::error_code &ec, std::size_t bytes);
    void handle_start(const boost::system::error_code &ec);
    void handle_init(const boost::system::error_code &ec);
    void handle_timeout(const boost::system::error_code &ec);

    friend class MRC1Initializer;

    boost::asio::io_service &m_io_service;
    boost::asio::deadline_timer m_timeout_timer;
    boost::posix_time::time_duration m_timeout;
    MessagePtr m_current_command;
    ResponseHandler m_current_response_handler;
    std::string m_write_buffer;
    boost::asio::streambuf m_read_buffer;
    Status m_status;
    MRC1ReplyParser m_reply_parser;
    boost::system::error_code m_last_error;
};

class MRC1SerialConnection: public MRC1Connection
{
  public:
    MRC1SerialConnection(boost::asio::io_service &io_service,
        const std::string &serial_device, unsigned int baud_rate = 9600);

  protected:
    virtual void start_impl(ErrorCodeCallback completion_handler);
    virtual void stop_impl();
    virtual void cancel_io();
    virtual void start_write_impl(
        const std::string &data,
        ReadWriteCallback completion_handler);

    virtual void start_read_impl(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler);

    virtual void start_read_line_impl(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler);

  private:
    std::string m_serial_device;
    unsigned int m_baud_rate;
    boost::asio::serial_port m_port;
};

class MRC1TCPConnection: public MRC1Connection
{
  public:
    MRC1TCPConnection(boost::asio::io_service &io_service,
        const std::string &address, unsigned short port);

    MRC1TCPConnection(boost::asio::io_service &io_service,
        const std::string &address, const std::string &service);

  protected:
    virtual void start_impl(ErrorCodeCallback completion_handler);
    virtual void stop_impl();
    virtual void cancel_io();
    virtual void start_write_impl(
        const std::string &data,
        ReadWriteCallback completion_handler);

    virtual void start_read_impl(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler);

    virtual void start_read_line_impl(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler);

  private:
    std::string m_host;
    std::string m_service;
    boost::asio::ip::tcp::socket m_socket;
    boost::asio::ip::tcp::resolver m_resolver;
};

} // namespace mesycontrol

#endif
