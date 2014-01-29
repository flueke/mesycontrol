cmake_minimum_required(VERSION 2.8)
project(enums-foo)

#set(CMAKE_CXX_FLAGS   "${CMAKE_CXX_FLAGS} -std=c++0x")

set(MY_TARGET "enum-string-conversion-cpp")

set(MY_SRCS main.cc enums.cc)

include_directories(
   ${CMAKE_CURRENT_BINARY_DIR}
   ${CMAKE_CURRENT_SOURCE_DIR}
   ${Boost_INCLUDE_DIRS}
)

add_executable(${MY_TARGET} ${MY_SRCS})
#target_link_libraries(${SERVER_TARGET} ${Boost_LIBRARIES})
