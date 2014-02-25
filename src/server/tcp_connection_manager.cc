#include <algorithm>
#include <boost/bind.hpp>
#include "tcp_connection_manager.h"

namespace mesycontrol
{

void TCPConnectionManager::start(TCPConnectionPtr c)
{
    connections_.insert(c);
    c->start();
}

void TCPConnectionManager::stop(TCPConnectionPtr c)
{
    connections_.erase(c);
    c->stop();
}

void TCPConnectionManager::stop_all()
{
    std::for_each(connections_.begin(), connections_.end(),
            boost::bind(&TCPConnection::stop, _1));
    connections_.clear();
}

} // namespace mesycontrol
