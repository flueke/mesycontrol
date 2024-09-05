if (CMAKE_VERSION VERSION_GREATER_EQUAL 3.30)
    cmake_policy(SET CMP0167 NEW)
endif()

set(Boost_USE_MULTITHREADED ON)
set(Boost_USE_STATIC_LIBS   ON)
find_package(Boost 1.67 REQUIRED COMPONENTS chrono program_options system date_time log log_setup log regex thread)
find_package(Threads REQUIRED)

set(Protobuf_USE_STATIC_LIBS OFF)
find_package(Protobuf REQUIRED)
find_package(absl REQUIRED)

include_directories(${Boost_INCLUDE_DIRS} ${PROTOBUF_INCLUDE_DIRS})

#if(NOT WIN32)
#    set(CMAKE_FIND_LIBRARY_SUFFIXES .a ${CMAKE_FIND_LIBRARY_SUFFIXES})
#    find_library(PROTOBUF_STATIC protobuf NAMES libprotobuf.a)
#    MESSAGE(STATUS "Using static protobuf library ${PROTOBUF_STATIC}")
#    set(PROTOBUF_LIBRARY ${PROTOBUF_STATIC})
#endif()

#include_directories(${CMAKE_CURRENT_BINARY_DIR})
PROTOBUF_GENERATE_CPP(PROTO_SRCS PROTO_HDRS ${MESYCONTROL_PROTO_IN})

add_executable(mesycontrol_server
    logging.cc
    main.cc
    mrc_comm.cc
    mrc1_connection.cc
    mrc1_reply_parser.cc
    mrc1_request_queue.cc
    poller.cc
    protocol.cc
    tcp_connection.cc
    tcp_connection.cc
    tcp_connection_manager.cc
    tcp_server.cc
    ${MESYCONTROL_GLOBAL_SOURCES}
    ${PROTO_SRCS} ${PROTO_HDRS})

target_link_libraries(mesycontrol_server
    PRIVATE Boost::disable_autolinking
    PRIVATE ${Boost_LIBRARIES}
    PRIVATE ${CMAKE_THREAD_LIBS_INIT}
    PRIVATE ${Protobuf_LIBRARIES}
    PRIVATE absl::log_internal_check_op
    PRIVATE absl::log_internal_message
    )

target_compile_definitions(mesycontrol_server PRIVATE -DBOOST_BIND_GLOBAL_PLACEHOLDERS)
target_compile_features(mesycontrol_server PRIVATE cxx_std_14)
target_include_directories(mesycontrol_server PRIVATE ${CMAKE_CURRENT_BINARY_DIR})

option(BOOST_ASIO_ENABLE_HANDLER_TRACKING "enable boost::asio handler tracking" OFF)
option(BOOST_ASIO_ENABLE_BUFFER_DEBUGGING "enable boost::asio buffer debugging" OFF)

if(BOOST_ASIO_ENABLE_HANDLER_TRACKING)
    target_compile_definitions(mesycontrol_server PRIVATE BOOST_ASIO_ENABLE_HANDLER_TRACKING)
endif()

if(BOOST_ASIO_ENABLE_BUFFER_DEBUGGING)
    target_compile_definitions(mesycontrol_server PRIVATE BOOST_ASIO_ENABLE_BUFFER_DEBUGGING)
endif()

if(WIN32)
    # Link against the DLLs needed by boost::asio
    target_link_libraries(mesycontrol_server PRIVATE ws2_32 wsock32)
    # Statically link against the GCC and C++ libraries to avoid
    # depending on DLLs installed with MinGW.
    target_link_options(mesycontrol_server PRIVATE -static-libgcc -static-libstdc++)
else(WIN32)
    target_link_libraries(mesycontrol_server PRIVATE rt)
endif(WIN32)

if (CMAKE_SYSTEM_NAME STREQUAL "Linux" AND CMAKE_SYSTEM_PROCESSOR STREQUAL "armv7l")
    target_link_libraries(mesycontrol_server PRIVATE atomic)
endif()

install(TARGETS mesycontrol_server RUNTIME DESTINATION bin)

# vim:tw=0
