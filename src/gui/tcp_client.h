#ifndef UUID_5ea71e49_6caf_4643_8009_8c6a6194fc52
#define UUID_5ea71e49_6caf_4643_8009_8c6a6194fc52

#include "config.h"
#include <boost/asio.hpp>
#include <boost/enable_shared_from_this.hpp>
#include <boost/noncopyable.hpp>
#include <boost/scoped_ptr.hpp>
#include <deque>
#include <string>
#include <mesycontrol/protocol.h>
#include "handler_types.h"

namespace mesycontrol
{

class TCPClient:
  public boost::enable_shared_from_this<TCPClient>,
  private boost::noncopyable
{
  public:
    explicit TCPClient(boost::asio::io_service &io_service);

    void connect_to(const std::string &hostname, const std::string &service_or_port);
    void disconnect() { if(socket_.is_open()) socket_.close(); }
    bool is_connected() const { return socket_.is_open(); }
    void stop() {
      disconnect();
      work_.reset();
    }

    void queue_request(protocol::Message request, ResponseHandler response_handler);
    size_t get_queue_size() const { return requests_.size(); }

  private:
    void handle_resolve(const boost::system::error_code &ec, boost::asio::ip::tcp::resolver::iterator it);
    void handle_connect(const boost::system::error_code& ec, boost::asio::ip::tcp::resolver::iterator it);

    void start_write_request();
    void handle_write_request(const boost::system::error_code &ec, size_t n_bytes);

    void start_read_response_size();
    void handle_read_response_size(const boost::system::error_code &ec, size_t n_bytes);

    void start_read_response();
    void handle_read_response(const boost::system::error_code &ec, size_t n_bytes);

    boost::asio::io_service &io_service_;

    boost::asio::ip::tcp::resolver resolver_;
    boost::asio::ip::tcp::socket socket_;

    std::string hostname_;
    std::string port_;

    typedef std::deque<std::pair<protocol::Message, ResponseHandler> > RequestQueue;

    RequestQueue requests_;

    uint16_t request_size_;
    std::vector<unsigned char> request_buf_;

    uint16_t response_size_;
    std::vector<unsigned char> response_buf_;
    
    boost::scoped_ptr<boost::asio::io_service::work> work_;
};

} // namespace mesycontrol

#endif
