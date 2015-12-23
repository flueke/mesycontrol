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
#include "logging.h"
#include "mrc1_reply_parser.h"
#include "mrc_comm.h"

namespace mesycontrol
{

class MRC1Connection:
  public boost::enable_shared_from_this<MRC1Connection>,
  private boost::noncopyable
{
  public:
    /** Default timeout for read/write operations. */
    static const boost::posix_time::time_duration default_io_timeout;

    /** Default timeout between reconnect attempts. */
    static const boost::posix_time::time_duration default_reconnect_timeout;

    typedef boost::function<void (
        const proto::MRCStatus::StatusCode &,
        const boost::system::error_code &,
        const std::string &, bool)>
      StatusChangeCallback;

    MRC1Connection(boost::asio::io_service &io_service);

    /** Start the connection. Opens the connection and performs the MRC
     * initialization sequence. */
    void start();

    /** Stop the connection. Cancels pending commands and closes the
     * connection. Use start() to start it again. */
    void stop();

    /** Send the given \c command to the MRC1, using the given \c
     * response_handler as a response callback.
     * Returns false if the connection has been stopped or a command is already
     * in progress. Otherwise true is returned and the command will be handled. */
    bool write_command(const MessagePtr &command,
        ResponseHandler response_handler);

    bool command_in_progress() const { return m_current_command != nullptr; }

    boost::posix_time::time_duration get_io_timeout() const { return m_io_timeout; }
    void set_io_timeout(const boost::posix_time::time_duration &timeout) { m_io_timeout = timeout; }

    boost::posix_time::time_duration get_reconnect_timeout() const { return m_reconnect_timeout; }
    void set_reconnect_timeout(const boost::posix_time::time_duration &timeout) { m_reconnect_timeout = timeout; }

    bool get_auto_reconnect() const { return m_auto_reconnect; }
    void set_auto_reconnect(bool auto_reconnect) { m_auto_reconnect = auto_reconnect; }

    proto::MRCStatus::StatusCode get_status() const { return m_status; }
    bool is_initializing() const { return m_status == proto::MRCStatus::INITIALIZING; }
    bool is_running() const { return m_status == proto::MRCStatus::RUNNING; }
    bool is_stopped() const;
    bool is_silenced() const { return m_silenced; }
    void set_silenced(bool silenced) { m_silenced = silenced; }
    boost::system::error_code get_last_error() const { return m_last_error; }
    boost::asio::io_service &get_io_service() { return m_io_service; }

    void register_status_change_callback(const StatusChangeCallback &callback);

    virtual ~MRC1Connection() {};

  protected:
    typedef boost::function<void (const boost::system::error_code, std::size_t)>
      ReadWriteCallback;

    typedef boost::function<void (const boost::system::error_code)>
      ErrorCodeCallback;

    /** Start an async write of the given data, using the given completion handler.
     * The caller has to ensure the reference to data remains valid until the
     * write completes so no copy has to be created. */
    void start_write(
        const std::string &data, 
        ReadWriteCallback completion_handler);

    void start_read(MRCComm::ReadHandler read_handler);

#if 0
    void start_read(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler);

    void start_read_line(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler);
#endif

    /** Start implementation. Open files here / resolve hostnames, etc.
     * Call the given completion_handler once startup is complete. */
    virtual void start_impl(ErrorCodeCallback completion_handler) = 0;

    /** Stop implementation. Close files, etc. */
    virtual void stop_impl() = 0;

    /** Cancel pending async IO requests. */
    virtual void cancel_io() = 0;

#if 0
    virtual void start_write_impl(
        const std::string &data,
        ReadWriteCallback completion_handler) = 0;

    virtual void start_read_impl(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler) = 0;

    virtual void start_read_line_impl(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler) = 0;
#endif

    virtual void handle_init(const boost::system::error_code ec);

    static const std::string response_line_terminator;
    static const char command_terminator;

    void set_comm(boost::shared_ptr<MRCComm> comm)
    { m_comm = comm; }

    boost::shared_ptr<MRCComm> get_comm() const
    { return m_comm; }

  private:
    void handle_write_command(const boost::system::error_code &ec, std::size_t bytes);
    //void handle_read_line(const boost::system::error_code &ec, std::size_t bytes);
    void handle_start(const boost::system::error_code &ec);
    void handle_io_timeout(const boost::system::error_code &ec);
    void handle_reconnect_timeout(const boost::system::error_code &ec);
    void stop(const boost::system::error_code &reason,
        proto::MRCStatus::StatusCode new_status = proto::MRCStatus::STOPPED);
    void reconnect_if_enabled();
    void set_status(
        const proto::MRCStatus::StatusCode &status,
        const boost::system::error_code &reason = boost::system::error_code(),
        const std::string &version = std::string(),
        bool has_read_multi = false);

    void handle_command_response_read(const boost::system::error_code &ec, const std::string &data);

    friend class MRC1Initializer;

    boost::asio::io_service &m_io_service;
    boost::asio::deadline_timer m_timeout_timer;
    boost::posix_time::time_duration m_io_timeout;
    boost::posix_time::time_duration m_reconnect_timeout;
    MessagePtr m_current_command;
    ResponseHandler m_current_response_handler;
    std::string m_write_buffer;
    boost::asio::streambuf m_read_buffer;
    proto::MRCStatus::StatusCode m_status;
    MRC1ReplyParser m_reply_parser;
    boost::system::error_code m_last_error;
    bool m_silenced;
    bool m_auto_reconnect;
    std::vector<StatusChangeCallback> m_status_change_callbacks;
    boost::shared_ptr<MRCComm> m_comm;

  protected:
    log::Logger m_log;
};

class MRC1SerialConnection: public MRC1Connection
{
  public:
    MRC1SerialConnection(boost::asio::io_service &io_service,
        const std::string &serial_device, unsigned int baud_rate = 0);

    static const std::vector<unsigned int> default_baud_rates;

  protected:
    virtual void start_impl(ErrorCodeCallback completion_handler);
    virtual void stop_impl();
    virtual void cancel_io();
#if 0
    virtual void start_write_impl(
        const std::string &data,
        ReadWriteCallback completion_handler);

    virtual void start_read_impl(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler);

    virtual void start_read_line_impl(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler);
#endif

    virtual void handle_init(
        const boost::system::error_code &ec);

  private:
    unsigned int get_baud_rate();
    void set_next_baud_rate();

    std::string m_serial_device;
    unsigned int m_requested_baud_rate;
    size_t m_current_baud_rate_idx;
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
#if 0
    virtual void start_write_impl(
        const std::string &data,
        ReadWriteCallback completion_handler);

    virtual void start_read_impl(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler);

    virtual void start_read_line_impl(
        boost::asio::streambuf &read_buffer,
        ReadWriteCallback completion_handler);
#endif

  private:
    std::string m_host;
    std::string m_service;
    boost::asio::ip::tcp::socket m_socket;
    boost::asio::ip::tcp::resolver m_resolver;
};

} // namespace mesycontrol

#endif
