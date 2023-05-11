configure_file("git_sha1.cc.in" "git_sha1.cc" @ONLY)
configure_file("config.in.h" "config.h" ESCAPE_QUOTES @ONLY)

set(MESYCONTROL_GLOBAL_SOURCES "${CMAKE_CURRENT_BINARY_DIR}/git_sha1.cc")
set(MESYCONTROL_PROTO_IN "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol.proto")
set(PROTOBUF_IMPORT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}")

include_directories(${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR})

option(MESYCONTROL_BUILD_SERVER "Build the mesycontrol server binary" ON)
option(MESYCONTROL_BUILD_CLIENT "Build the mesycontrol GUI client binary (requires pyinstaller!)" OFF)

if (MESYCONTROL_BUILD_SERVER)
	add_subdirectory(server)
endif()

if (MESYCONTROL_BUILD_CLIENT)
	add_subdirectory(client)
endif()

# vim:tw=0
