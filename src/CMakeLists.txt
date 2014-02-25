set(Boost_USE_STATIC_LIBS   OFF)

if (WIN32) # Use static boost libraries for windows builds.
    set(Boost_USE_STATIC_LIBS ON)
endif(WIN32)

set(Boost_USE_MULTITHREADED ON)

find_package(Boost 1.46 REQUIRED COMPONENTS program_options system date_time regex thread)
find_package(Threads REQUIRED)

include_directories(${Boost_INCLUDE_DIRS} ${CMAKE_CURRENT_BINARY_DIR})

configure_file("config.in.h" "config.h" ESCAPE_QUOTES)

set(MESYCONTROL_LIB_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/protocol.cc")

add_subdirectory(cli)
add_subdirectory(gui)
add_subdirectory(server)
