cmake_minimum_required(VERSION 2.8)
project(qxtrpc-mutex-wait)

set(QXT_USE_QXTCORE     TRUE)
set(QXT_USE_QXTNETWORK  TRUE)
include(${CMAKE_SOURCE_DIR}/QxtConfig.cmake)

set(CMAKE_CXX_FLAGS   "${CMAKE_CXX_FLAGS} -std=c++0x")
set(CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/")

find_package(Qt4 4.8 REQUIRED QtCore QtNetwork)
include(${QT_USE_FILE})

set(Boost_USE_STATIC_LIBS ON)
set(Boost_USE_MULTITHREADED ON)
find_package(Boost 1.46 REQUIRED COMPONENTS thread)

set(SERVER_TARGET "testserver")
set(CLIENT_TARGET "testclient")

qt4_wrap_cpp(SERVER_MOC_OUT server.h)
qt4_wrap_cpp(CLIENT_MOC_OUT client.h)

include_directories(
   ${CMAKE_CURRENT_BINARY_DIR}
   ${CMAKE_CURRENT_SOURCE_DIR}
   ${Boost_INCLUDE_DIRS}
)

add_executable(${SERVER_TARGET} server.cc servermain.cc ${SERVER_MOC_OUT})
add_executable(${CLIENT_TARGET} client.cc clientmain.cc ${CLIENT_MOC_OUT})

target_link_libraries(${SERVER_TARGET} ${Boost_LIBRARIES} ${QT_LIBRARIES}
   ${QXT_LIBRARIES})

target_link_libraries(${CLIENT_TARGET} ${Boost_LIBRARIES} ${QT_LIBRARIES}
   ${QXT_LIBRARIES})
