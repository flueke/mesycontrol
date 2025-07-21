# To make the server binary start under ubuntu 24.04 libprotobuf.so.23 is
# needed. The stuff below tries to pick exactly that and its dependencies.

file(GET_RUNTIME_DEPENDENCIES
    RESOLVED_DEPENDENCIES_VAR server_deps
    POST_EXCLUDE_REGEXES ".*ld-linux.*" ".*libc\\.so.*" ".*libgcc_s\\.so.*" ".*libstdc\\+\\+\\.so.*" ".*libm\\.so.*" ".*libz\\.so.*"
    EXECUTABLES ${CMAKE_INSTALL_PREFIX}/bin/mesycontrol_server)

message(STATUS "Installing additional dependencies for mesycontrol_server: ${server_deps}")

file(INSTALL ${server_deps}
    DESTINATION ${CMAKE_INSTALL_PREFIX}/lib
    FOLLOW_SYMLINK_CHAIN
)
