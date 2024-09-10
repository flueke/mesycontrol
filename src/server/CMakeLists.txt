if (CMAKE_VERSION VERSION_GREATER_EQUAL 3.30)
    cmake_policy(SET CMP0167 NEW)
endif()

set(Boost_USE_MULTITHREADED ON)
set(Boost_USE_STATIC_LIBS   ON)
find_package(Boost 1.67 REQUIRED COMPONENTS chrono program_options system date_time log log_setup log regex thread)
find_package(Threads REQUIRED)

# https://stackoverflow.com/a/74545214 and https://stackoverflow.com/a/75299170
message("Fetching protobuf")
set(protobuf_VERBOSE ON)
set(protobuf_INSTALL OFF)
set(protobuf_BUILD_TESTS OFF)
set(protobuf_BUILD_SHARED_LIBS OFF)
set(protobuf_BUILD_PROTOC_BINARIES ON)
#set(protobuf_MSVC_STATIC_RUNTIME OFF)

include(FetchContent)
FetchContent_Declare(protobuf
  GIT_REPOSITORY https://github.com/protocolbuffers/protobuf.git
  GIT_TAG        v21.12
  OVERRIDE_FIND_PACKAGE
)

FetchContent_MakeAvailable(protobuf)
FetchContent_GetProperties(protobuf)
#find_package(protobuf CONFIG REQUIRED)

#if(NOT WIN32)
#    set(CMAKE_FIND_LIBRARY_SUFFIXES .a ${CMAKE_FIND_LIBRARY_SUFFIXES})
#    find_library(PROTOBUF_STATIC protobuf NAMES libprotobuf.a)
#    MESSAGE(STATUS "Using static protobuf library ${PROTOBUF_STATIC}")
#    set(PROTOBUF_LIBRARY ${PROTOBUF_STATIC})
#endif()

include_directories(${CMAKE_CURRENT_BINARY_DIR})

#protobuf_generate_cpp(PROTO_SRCS PROTO_HDRS ${MESYCONTROL_PROTO_IN})
set(PROTO_HDRS "${CMAKE_CURRENT_BINARY_DIR}/mesycontrol.pb.h")
set(PROTO_SRCS "${CMAKE_CURRENT_BINARY_DIR}/mesycontrol.pb.cpp")
set(PROTOC ${protobuf_BINARY_DIR}/protoc)

add_custom_command(
    OUTPUT ${PROTO_HDRS} ${PROTO_SRCS}
    COMMAND ${PROTOC} -I ${PROTOBUF_IMPORT_DIRS} --cpp_out ${CMAKE_CURRENT_BINARY_DIR} ${MESYCONTROL_PROTO_IN}
    DEPENDS ${PROTOC} ${MESYCONTROL_PROTO_IN}
)
message("PROTO_SRCS=${PROTO_SRCS}")

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
    ${PROTO_SRCS}
    ${PROTO_HDRS}
    )

target_link_libraries(mesycontrol_server
    PRIVATE Boost::disable_autolinking
    PRIVATE ${Boost_LIBRARIES}
    PRIVATE Threads::Threads
    PRIVATE protobuf::libprotobuf
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
