find_package(Qt4 4.8 REQUIRED QtCore QtGui QtNetwork)
include(${QT_USE_FILE})

set(MESYCONTROL_GUI_TARGET "mesycontrol_gui")

set(MESYCONTROL_GUI_SRCS
  main.cc
  qt_tcp_client.cc
  tcp_client.cc
  mainwin.cc
)

set(MESYCONTROL_GUI_MOC_HDRS
  qt_tcp_client.h
  mainwin.h
)

qt4_wrap_cpp(MESYCONTROL_GUI_MOC_OUT ${MESYCONTROL_GUI_MOC_HDRS})

add_executable(${MESYCONTROL_GUI_TARGET} ${MESYCONTROL_GUI_SRCS} ${MESYCONTROL_LIB_SOURCES}
  ${MESYCONTROL_GUI_MOC_OUT})

target_link_libraries(${MESYCONTROL_GUI_TARGET} ${Boost_LIBRARIES}
  ${CMAKE_THREAD_LIBS_INIT} ${QT_LIBRARIES})

if(WIN32)
    # Statically link against the GCC and C++ libraries to avoid
    # depending
    # on DLLs installed with MinGW.
    set(CMAKE_EXE_LINKER_FLAGS "-static-libgcc -static-libstdc++")
    # Link against the DLLs needed by boost::asio
    set(WINDOWS_LIBS ws2_32 wsock32)
    target_link_libraries(${MESYCONTROL_GUI_TARGET} ${WINDOWS_LIBS})
endif(WIN32)

# vim:tw=0
