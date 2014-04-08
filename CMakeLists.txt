cmake_minimum_required(VERSION 2.8)
project(mesycontrol)

# Create binaries in the root of the build directory
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

# Add the local cmake directory to the module path
list(APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")

# Add the root build directory and the source include directory to the
# compiler search path.
include_directories(${CMAKE_CURRENT_BINARY_DIR})
include_directories("${CMAKE_SOURCE_DIR}/include")

add_subdirectory(src)
add_subdirectory(doc)

set(CPACK_GENERATOR "TBZ2")
set(CPACK_PACKAGE_FILE_NAME "${CMAKE_PROJECT_NAME}-${CMAKE_SYSTEM}")
include(CPack)

# vim:tw=0
