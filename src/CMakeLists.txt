set(Boost_USE_STATIC_LIBS   OFF)

if (WIN32) # Use static boost libraries for windows builds.
    set(Boost_USE_STATIC_LIBS ON)
endif(WIN32)

set(Boost_USE_MULTITHREADED ON)

find_package(Boost 1.46 REQUIRED COMPONENTS program_options system date_time regex thread)
find_package(Threads REQUIRED)

include_directories(${Boost_INCLUDE_DIRS} ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR})

include(GetGitRevisionDescription)
get_git_head_revision(GIT_REFSPEC GIT_SHA1)

configure_file("git_sha1.cc.in" "git_sha1.cc" @ONLY)
configure_file("config.in.h" "config.h" ESCAPE_QUOTES @ONLY)

set(MESYCONTROL_GLOBAL_SOURCES "${CMAKE_CURRENT_BINARY_DIR}/git_sha1.cc")

add_subdirectory(server)

# vim:tw=0
