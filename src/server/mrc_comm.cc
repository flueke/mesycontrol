#include "mrc_comm.h"

namespace mesycontrol
{

void MRCComm::write(const std::string &data, WriteHandler handler)
{
  if (m_busy)
    throw std::runtime_error("MRCComm is busy");

  m_busy = true;
  m_str_buf  = data;
  m_write_handler = handler;
  start_write(m_str_buf.begin());
}

void MRCComm::read(ReadHandler handler)
{
  if (m_busy)
    throw std::runtime_error("MRCComm is busy");

  m_busy = true;
  m_str_buf.clear();
  m_read_handler = handler;
  start_read();
}

void MRCComm::read_until_prompt(ReadHandler handler)
{
  if (m_busy)
    throw std::runtime_error("MRCComm is busy");

  m_busy = true;
  m_str_buf.clear();
  m_read_handler = handler;

  m_timer.expires_from_now(default_read_until_prompt_timeout);

  m_timer.async_wait(boost::bind(&MRCComm::handle_read_until_prompt_timeout,
        shared_from_this(), _1));

  start_read_until_prompt(m_asio_buf,
      boost::bind(&MRCComm::finish_read_until_prompt, shared_from_this(), _1, _2));
}

void MRCComm::finish_read_until_prompt(const boost::system::error_code &ec, std::size_t sz)
{
  BOOST_LOG_SEV(m_log, log::lvl::debug)
    << "MRCComm::finish_read_until_prompt: ec=" << ec.message()
    << ", sz=" << sz;

  m_timer.cancel();
  std::string data;

  if (!ec) {
    auto buffers = m_asio_buf.data();
    data = std::string(asio::buffers_begin(buffers), asio::buffers_end(buffers));
  }

  m_io.post(boost::bind(m_read_handler, ec, data));

  m_asio_buf.consume(m_asio_buf.size());
  m_busy = false;
  m_read_handler = 0;
}

void MRCComm::handle_read_until_prompt_timeout(boost::system::error_code ec)
{
  if (ec != asio::error::operation_aborted &&
      m_timer.expires_at() <= asio::deadline_timer::traits_type::now()) {
    cancel_io();
    m_busy = false;
  }
}

void MRCComm::handle_timeout(boost::system::error_code ec)
{
  if (ec != asio::error::operation_aborted &&
      m_timer.expires_at() <= asio::deadline_timer::traits_type::now()) {

    //BOOST_LOG_SEV(m_log, log::lvl::warning)
    //  << "MRCComm::handle_timeout: canceling IO operation due to timeout";

    cancel_io();
    m_busy = false;
  }
}

void MRCComm::start_write(const std::string::const_iterator &it)
{
  if (it == m_str_buf.end()) {
    finish_write(it, boost::system::error_code());
  } else {
    m_timer.expires_from_now(m_write_timeout);
    m_timer.async_wait(boost::bind(&MRCComm::handle_timeout, shared_from_this(), _1));
    start_write_one(it, boost::bind(&MRCComm::handle_write, shared_from_this(), it, _1, _2));
  }
}

void MRCComm::handle_write(std::string::const_iterator it, boost::system::error_code ec, std::size_t sz)
{
  if (!ec) {
    m_timer.cancel();
    start_write(++it);
  } else {
    finish_write(it, ec);
  }
}

void MRCComm::finish_write(std::string::const_iterator it, boost::system::error_code ec)
{
  m_timer.cancel();
  m_io.post(boost::bind(m_write_handler, ec, it - m_str_buf.begin()));
  m_busy = false;
  m_write_handler = 0;
  m_str_buf.clear();
}

void MRCComm::start_read()
{
  m_timer.expires_from_now(m_read_timeout);
  m_timer.async_wait(boost::bind(&MRCComm::handle_timeout, shared_from_this(), _1));
  start_read_one(m_char_buf, boost::bind(&MRCComm::handle_read, shared_from_this(), _1, _2));
}

void MRCComm::handle_read(const boost::system::error_code &ec, std::size_t sz)
{
  if (!ec) {
    m_timer.cancel();
    m_str_buf.push_back(m_char_buf);
    start_read();
  } else {
    finish_read(ec);
  }
}

void MRCComm::finish_read(const boost::system::error_code &ec)
{
  BOOST_LOG_SEV(m_log, log::lvl::trace)
    << "MRCComm::finish_read: ec=" << ec.message();

  m_timer.cancel();
  m_io.post(boost::bind(m_read_handler,
        ec == boost::system::errc::operation_canceled ? boost::system::error_code() : ec,
        m_str_buf));
  m_busy = false;
  m_read_handler = 0;
  m_str_buf.clear();
}

} // ns mesycontrol
