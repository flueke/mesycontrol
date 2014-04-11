set(Boost_USE_MULTITHREADED ON)
set(Boost_USE_STATIC_LIBS  ON)

if (WIN32) # Use static boost libraries for windows builds.
    set(Boost_USE_STATIC_LIBS ON)
endif(WIN32)

find_package(Boost 1.54 REQUIRED COMPONENTS chrono program_options system date_time log regex thread)
find_package(Threads REQUIRED)

include_directories(${Boost_INCLUDE_DIRS})

set(MESYCONTROL_SERVER_TARGET "mesycontrol_server")

set(MESYCONTROL_SERVER_SRCS
    tcp_connection.cc
    main.cc
    mrc1_connection.cc
    mrc1_reply_parser.cc
    protocol.cc
    request_dispatcher.cc
    tcp_connection.cc
    tcp_connection_manager.cc
    tcp_server.cc
)

option(BOOST_ASIO_ENABLE_HANDLER_TRACKING "enable boost::asio handler tracking")
option(BOOST_ASIO_ENABLE_BUFFER_DEBUGGING "enable boost::asio buffer debugging")

add_executable(${MESYCONTROL_SERVER_TARGET} ${MESYCONTROL_SERVER_SRCS} ${MESYCONTROL_GLOBAL_SOURCES})
target_link_libraries(${MESYCONTROL_SERVER_TARGET} ${Boost_LIBRARIES} ${CMAKE_THREAD_LIBS_INIT})

if(WIN32)
    # Statically link against the GCC and C++ libraries to avoid
    # depending on DLLs installed with MinGW.
    set(CMAKE_EXE_LINKER_FLAGS "-static-libgcc -static-libstdc++")
    # Link against the DLLs needed by boost::asio
    set(WINDOWS_LIBS ws2_32 wsock32)
    target_link_libraries(${MESYCONTROL_SERVER_TARGET} ${WINDOWS_LIBS})
else(WIN32)
    target_link_libraries(${MESYCONTROL_SERVER_TARGET} rt)
endif(WIN32)

install(TARGETS ${MESYCONTROL_SERVER_TARGET} RUNTIME DESTINATION bin)

# vim:tw=0
