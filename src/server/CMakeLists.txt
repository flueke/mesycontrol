set(Boost_USE_MULTITHREADED ON)
set(Boost_USE_STATIC_LIBS   ON)

if (WIN32) # Use static boost libraries for windows builds.
    set(Boost_USE_STATIC_LIBS ON)
    add_definitions(-D_WIN32_WINNT=0x0501)
endif(WIN32)

find_package(Boost 1.54 REQUIRED COMPONENTS chrono program_options system date_time log_setup log regex thread)
find_package(Threads REQUIRED)
find_package(Protobuf REQUIRED)

include_directories(${Boost_INCLUDE_DIRS} ${PROTOBUF_INCLUDE_DIRS})

set(MESYCONTROL_SERVER_TARGET "mesycontrol_server")

set(MESYCONTROL_SERVER_SRCS
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
)

option(BOOST_ASIO_ENABLE_HANDLER_TRACKING "enable boost::asio handler tracking")
option(BOOST_ASIO_ENABLE_BUFFER_DEBUGGING "enable boost::asio buffer debugging")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++0x")

if (WIN32)
  # Boost uses -march=i686. To avoid linker warnings about duplicate sections
  # having different sizes this flag needs to be used by CMake aswell.
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -march=i686")
endif(WIN32)

if(NOT WIN32)
    set(CMAKE_FIND_LIBRARY_SUFFIXES .a ${CMAKE_FIND_LIBRARY_SUFFIXES})
    find_library(PROTOBUF_STATIC protobuf NAMES libprotobuf.a)
    MESSAGE(STATUS "Using static protobuf library ${PROTOBUF_STATIC}")
    set(PROTOBUF_LIBRARY ${PROTOBUF_STATIC})
endif()

include_directories(${CMAKE_CURRENT_BINARY_DIR})
PROTOBUF_GENERATE_CPP(PROTO_SRCS PROTO_HDRS ${MESYCONTROL_PROTO_IN})

add_executable(${MESYCONTROL_SERVER_TARGET}
    ${MESYCONTROL_SERVER_SRCS}
    ${MESYCONTROL_GLOBAL_SOURCES}
    ${PROTO_SRCS} ${PROTO_HDRS})

target_link_libraries(${MESYCONTROL_SERVER_TARGET}
    ${Boost_LIBRARIES}
    ${CMAKE_THREAD_LIBS_INIT}
    ${PROTOBUF_LIBRARY})

target_compile_definitions(${MESYCONTROL_SERVER_TARGET}
    PRIVATE -DBOOST_BIND_GLOBAL_PLACEHOLDERS)

if(WIN32)
    # Statically link against the GCC and C++ libraries to avoid
    # depending on DLLs installed with MinGW.
    set(CMAKE_EXE_LINKER_FLAGS "-static-libgcc -static-libstdc++")
    # Link against the DLLs needed by boost::asio
    set(WINDOWS_LIBS ws2_32 wsock32)
    target_link_libraries(${MESYCONTROL_SERVER_TARGET} ${WINDOWS_LIBS})

    # Find libwinpthread-1.dll (required when building with Qt's gcc)
    find_library(WINPTHREAD_1 winpthread-1 NAMES libwinpthread-1.dll)
    MESSAGE(STATUS "Found libwinpthread-1 at ${WINPTHREAD_1}")
else(WIN32)
    target_link_libraries(${MESYCONTROL_SERVER_TARGET} rt)
endif(WIN32)

if (CMAKE_SYSTEM_NAME STREQUAL "Linux" AND CMAKE_SYSTEM_PROCESSOR STREQUAL "armv7l")
    target_link_libraries(${MESYCONTROL_SERVER_TARGET} atomic)
endif()

install(TARGETS ${MESYCONTROL_SERVER_TARGET} RUNTIME DESTINATION bin)

if(WIN32)
  install(FILES ${WINPTHREAD_1} DESTINATION bin)
endif(WIN32)

#add_subdirectory(test)

# vim:tw=0
