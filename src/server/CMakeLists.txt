set(MESYCONTROL_SERVER_TARGET "mesycontrol_server")

set(MESYCONTROL_SERVER_SRCS
    tcp_connection.cc
    main.cc
    mrc1_connection.cc
    mrc1_reply_parser.cc
    request_dispatcher.cc
    tcp_connection.cc
    tcp_connection_manager.cc
    tcp_server.cc
)

add_executable(${MESYCONTROL_SERVER_TARGET} ${MESYCONTROL_SERVER_SRCS} ${MESYCONTROL_LIB_SOURCES})
target_link_libraries(${MESYCONTROL_SERVER_TARGET} ${Boost_LIBRARIES} ${CMAKE_THREAD_LIBS_INIT})

if(WIN32)
    # Statically link against the GCC and C++ libraries to avoid
    # depending
    # on DLLs installed with MinGW.
    set(CMAKE_EXE_LINKER_FLAGS "-static-libgcc -static-libstdc++")
    # Link against the DLLs needed by boost::asio
    set(WINDOWS_LIBS ws2_32 wsock32)
    target_link_libraries(${MESYCONTROL_SERVER_TARGET} ${WINDOWS_LIBS})
endif(WIN32)
