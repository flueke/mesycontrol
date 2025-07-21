cmake_minimum_required(VERSION 3.16)
project(mesycontrol DESCRIPTION "Remote control for mesytec NIM devices")

set(MESYCONTROL_MAIN_PROJECT OFF)
if (CMAKE_CURRENT_SOURCE_DIR STREQUAL CMAKE_SOURCE_DIR)
    set(MESYCONTROL_MAIN_PROJECT ON)
endif()

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# RPATH handling
# https://gitlab.kitware.com/cmake/community/wikis/doc/cmake/RPATH-handling

# use, i.e. don't skip the full RPATH for the build tree
SET(CMAKE_SKIP_BUILD_RPATH FALSE)

# Enable $ORIGIN in the rpath if supported by the target platform.
SET(CMAKE_BUILD_RPATH_USE_ORIGIN TRUE)

SET(CMAKE_INSTALL_RPATH "$ORIGIN/../lib:$ORIGIN/")

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
string(REGEX REPLACE "^v(.*)" "\\1" GIT_VERSION ${GIT_VERSION}) # Remove a leading 'v' letter from the version string
string(REGEX MATCH "^([0-9.]+(-beta[0-9]*|-rc[0-9]*)?(-[0-9]+)?)" GIT_VERSION_SHORT ${GIT_VERSION})
string(REGEX MATCH "^([0-9.]+)" GIT_VERSION_TAG ${GIT_VERSION})

# Add the root build directory to the compiler search path.
include_directories(${CMAKE_CURRENT_BINARY_DIR})

add_subdirectory(src)

option(MESYCONTROL_BUILD_DOCS "Build documentation (if sphinx was found)" ${MESYCONTROL_MAIN_PROJECT})

if (MESYCONTROL_BUILD_DOCS)
    add_subdirectory(doc)
endif()

#install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/scripts/ DESTINATION share/scripts USE_SOURCE_PERMISSIONS)
install(FILES "${CMAKE_SOURCE_DIR}/LICENSE.TXT" DESTINATION share/doc/mesycontrol)


if ("${CMAKE_SIZEOF_VOID_P}" EQUAL "8")
    set(PACKAGE_ARCH_STRING "x64")
else()
    set(PACKAGE_ARCH_STRING "x32")
endif()

# Note: To produce stand-alone packages additional files need to be deployed to
# the target system: shared objects, Qt plugins, Qt configuration, shell
# scripts, etc.
#
# These files are handled using an external deploy directory which is added via
# the install() command.
#option(MESYCONTROL_INSTALL_DEPLOY_FILES "Install additional library files from a special deploy directory." OFF)

if (WIN32)
    set(CPACK_GENERATOR "NSIS") # "NSIS;ZIP"
    set(CPACK_NSIS_ENABLE_UNINSTALL_BEFORE_INSTALL "ON")
    set(CPACK_NSIS_PACKAGE_NAME "mesycontrol")
    set(CPACK_NSIS_MUI_FINISHPAGE_RUN "mesycontrol_gui.exe")
    set(CPACK_NSIS_URL_INFO_ABOUT "http://www.mesytec.com")
    set(CPACK_NSIS_CONTACT "info@mesytec.com")
    set(CPACK_NSIS_MENU_LINKS
        "share/doc/mesycontrol.pdf" "mesycontrol Documentation (PDF)"
        "share/doc/html/index.html" "mesycontrol Documentation (HTML)")
    set(CPACK_NSIS_MODIFY_PATH "ON")
    set(CPACK_SOURCE_GENERATOR "ZIP")
else()
    # This was intended for the Qt4 deploy files but these are now handled in the generated setup.py distutils script.
    #if (MESYCONTROL_INSTALL_DEPLOY_FILES)

    #    set(DEPLOY_SOURCE_DIR "$ENV{HOME}/src/mesycontrol-deploy/linux-${PACKAGE_ARCH_STRING}/")
    #    message("DEPLOY_SOURCE_DIR=${DEPLOY_SOURCE_DIR}")

    #    if (EXISTS $DEPLOY_SOURCE_DIR)
    #        # Install additional deployment files: shared objects, qt plugins, etc.
    #        install(DIRECTORY ${DEPLOY_SOURCE_DIR} DESTINATION .  USE_SOURCE_PERMISSIONS)
    #    endif()
    #endif()
    set(CPACK_GENERATOR "TBZ2")
    set(CPACK_SOURCE_GENERATOR "TBZ2")
endif(WIN32)

configure_file("CPackOptions.cmake.in" "${PROJECT_BINARY_DIR}/CPackOptions.cmake" @ONLY)
set(CPACK_PROJECT_CONFIG_FILE "${PROJECT_BINARY_DIR}/CPackOptions.cmake")

include(CPack)

# vim:tw=0
