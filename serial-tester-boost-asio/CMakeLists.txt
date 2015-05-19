cmake_minimum_required(VERSION 2.8)
project(aml-tester-boost-asio)

set(CMAKE_CXX_FLAGS   "${CMAKE_CXX_FLAGS} -std=c++0x")
set(CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/")

add_subdirectory(src)
