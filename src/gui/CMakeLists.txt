set(MESYCONTROL_GUI_TARGET "mesycontrol_gui")

set(MESYCONTROL_GUI_SRCS
  main.cc
  tcp_client.cc
)

add_executable(${MESYCONTROL_GUI_TARGET} ${MESYCONTROL_GUI_SRCS} ${MESYCONTROL_LIB_SOURCES})
target_link_libraries(${MESYCONTROL_GUI_TARGET} ${Boost_LIBRARIES} ${CMAKE_THREAD_LIBS_INIT})

if(WIN32)
    # Statically link against the GCC and C++ libraries to avoid
    # depending
    # on DLLs installed with MinGW.
    set(CMAKE_EXE_LINKER_FLAGS "-static-libgcc -static-libstdc++")
    # Link against the DLLs needed by boost::asio
    set(WINDOWS_LIBS ws2_32 wsock32)
    target_link_libraries(${MESYCONTROL_GUI_TARGET} ${WINDOWS_LIBS})
endif(WIN32)

