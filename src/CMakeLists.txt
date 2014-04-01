
include(GetGitRevisionDescription)
get_git_head_revision(GIT_REFSPEC GIT_SHA1)

configure_file("git_sha1.cc.in" "git_sha1.cc" @ONLY)
configure_file("config.in.h" "config.h" ESCAPE_QUOTES @ONLY)

set(MESYCONTROL_GLOBAL_SOURCES "${CMAKE_CURRENT_BINARY_DIR}/git_sha1.cc")
include_directories(${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR})

add_subdirectory(server)
add_subdirectory(client)

# vim:tw=0
