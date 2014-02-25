#ifndef UUID_04abdb37_fdb6_4230_8bab_1a9552408788
#define UUID_04abdb37_fdb6_4230_8bab_1a9552408788

#include "config.h"
#include <set>
#include <boost/noncopyable.hpp>
#include "tcp_connection.h"

namespace mesycontrol
{

class TCPConnectionManager: private boost::noncopyable
{
    public:
        /// Add the specified connection to the manager and start it.
        void start(TCPConnectionPtr c);

        /// Stop the specified connection.
        void stop(TCPConnectionPtr c);

        /// Stop all connections.
        void stop_all();

    private:
        /// The managed connections.
        std::set<TCPConnectionPtr> connections_;
};

} // namespace mesycontrol

#endif
