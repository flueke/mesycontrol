cmake_minimum_required(VERSION 2.8)
project(mesycontrol)

set(CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

include_directories(${CMAKE_CURRENT_BINARY_DIR})
include_directories("${CMAKE_SOURCE_DIR}/include")

add_subdirectory(src)
add_subdirectory(doc)
