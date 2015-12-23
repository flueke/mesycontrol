#include "mrc_comm.h"

namespace asio = boost::asio;

namespace mesycontrol
{

void MRCComm::write(const std::string &data, WriteHandler handler)
{
  if (m_busy)
    throw std::runtime_error("MRCComm is busy");

  m_busy = true;
  m_buf  = data;
  m_write_handler = handler;
  start_write(m_buf.begin());
}

void MRCComm::read(ReadHandler handler)
{
  if (m_busy)
    throw std::runtime_error("MRCComm is busy");

  m_busy = true;
  m_buf.clear();
  m_read_handler = handler;
  start_read();
}

void MRCComm::handle_timeout(boost::system::error_code ec)
{
  BOOST_LOG_SEV(m_log, log::lvl::debug)
    << "MRCComm::handle_timeout: ec=" << ec.message();

  if (ec != asio::error::operation_aborted &&
      m_timer.expires_at() <= asio::deadline_timer::traits_type::now()) {

    BOOST_LOG_SEV(m_log, log::lvl::warning)
      << "MRCComm::handle_timeout: canceling IO operation";

    cancel_io();
  }
}

void MRCComm::start_write(const std::string::const_iterator &it)
{
  if (it == m_buf.end()) {
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
  m_io.post(boost::bind(m_write_handler, ec, it - m_buf.begin()));
  m_busy = false;
  m_write_handler = 0;
  m_buf.clear();
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
    m_buf.push_back(m_char_buf);
    start_read();
  } else {
    finish_read(ec);
  }
}

void MRCComm::finish_read(const boost::system::error_code &ec)
{
  m_timer.cancel();
  m_io.post(boost::bind(m_read_handler,
        ec == boost::system::errc::operation_canceled ? boost::system::error_code() : ec,
        m_buf));
  m_busy = false;
  m_read_handler = 0;
  m_buf.clear();
}

} // ns mesycontrol
