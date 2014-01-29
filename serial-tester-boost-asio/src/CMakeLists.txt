set(Boost_USE_STATIC_LIBS   ON)
set(Boost_USE_MULTITHREADED ON)
find_package(Boost 1.46 REQUIRED COMPONENTS program_options system date_time
   regex thread)
find_package(Threads REQUIRED)

set(TESTER_TARGET "serial-tester-boost-asio")

set(TESTER_SRCS
   main.cc
)

include_directories(
   ${CMAKE_CURRENT_BINARY_DIR}
   ${CMAKE_CURRENT_SOURCE_DIR}
   ${Boost_INCLUDE_DIRS}
)

add_executable(${TESTER_TARGET} ${TESTER_SRCS})
target_link_libraries(${TESTER_TARGET} ${Boost_LIBRARIES} ${CMAKE_THREAD_LIBS_INIT})
