cmake_minimum_required(VERSION 2.8.3)
project(mesycontrol)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Create binaries in the root of the build directory
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

# Add the local cmake directory and the current source directory to the module
# path. The latter is needed for CMake/CPack to find and use NSIS.template.in.
list(APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")

# Pull information from git:
# GIT_SHA1 contains the complete git hash
# GIT_VERSION contains the name of the latest git tag and the start of the git hash if
# there have been changes since the tag has been created.
include(GetGitRevisionDescription)
get_git_head_revision(GIT_REFSPEC GIT_SHA1)
git_describe(GIT_VERSION "--always")

# Add the root build directory to the compiler search path.
include_directories(${CMAKE_CURRENT_BINARY_DIR})

add_subdirectory(src)
add_subdirectory(doc)

#install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/scripts/ DESTINATION share/scripts USE_SOURCE_PERMISSIONS)
install(FILES "${CMAKE_SOURCE_DIR}/LICENSE.TXT" DESTINATION .)

# CPack configuration used for 'make package'
if (WIN32)
  set(CPACK_PACKAGE_FILE_NAME "${CMAKE_PROJECT_NAME}-${GIT_VERSION}")
else(WIN32)
  execute_process(COMMAND uname -m COMMAND tr -d '\n' OUTPUT_VARIABLE ARCHITECTURE)
  set(CPACK_PACKAGE_FILE_NAME "${CMAKE_PROJECT_NAME}-${GIT_VERSION}-${ARCHITECTURE}")
endif(WIN32)

set(CPACK_PACKAGE_VERSION "${GIT_VERSION}")
set(CPACK_PACKAGE_VENDOR "mesytec")
set(CPACK_PACKAGE_EXECUTABLES "mesycontrol_gui;mesycontrol")
set(CPACK_PACKAGE_INSTALL_DIRECTORY "mesycontrol")
set(CPACK_OUTPUT_FILE_PREFIX "packages")
set(CPACK_RESOURCE_FILE_LICENSE "${CMAKE_SOURCE_DIR}/src/client/mesycontrol/resources/gpl-notice.txt")
set(CPACK_STRIP_FILES TRUE)

if (WIN32)
    set(CPACK_GENERATOR "ZIP" "NSIS")
    set(CPACK_NSIS_ENABLE_UNINSTALL_BEFORE_INSTALL "ON")
    set(CPACK_NSIS_PACKAGE_NAME "mesycontrol")
    set(CPACK_NSIS_MUI_FINISHPAGE_RUN "mesycontrol_gui.exe")
    set(CPACK_NSIS_URL_INFO_ABOUT "http://www.mesytec.com")
    set(CPACK_NSIS_CONTACT "info@mesytec.com")
    set(CPACK_NSIS_MENU_LINKS
        "share/doc/mesycontrol.pdf" "Documentation")
    set(CPACK_SOURCE_GENERATOR "ZIP")
else(WIN32)
    set(CPACK_GENERATOR "TBZ2" "STGZ")
    set(CPACK_SOURCE_GENERATOR "TBZ2")
endif(WIN32)

include(CPack)

# vim:tw=0
