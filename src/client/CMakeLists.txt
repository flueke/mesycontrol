find_package(PythonInterp REQUIRED)
find_package(Protobuf REQUIRED)

set(SETUP_PY_IN   "${CMAKE_CURRENT_SOURCE_DIR}/setup.py.in")
set(SETUP_PY      "${CMAKE_CURRENT_BINARY_DIR}/setup.py")

set(VERSION_PY_IN "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/mc_version.py.in")
set(VERSION_PY    "${CMAKE_CURRENT_BINARY_DIR}/mesycontrol/mc_version.py")

set(STAMP         "${CMAKE_CURRENT_BINARY_DIR}/build/timestamp")

# Note: The resources file is updated directly inside the source tree before
# being included in the cx_freeze library.zip by running setup.py.
set(PYRCC       "pyrcc4")
set(QRC_IN      "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/resources.qrc")
set(QRC_OUT     "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/resources.py")

set(PROTO_PY_OUT "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/mesycontrol_pb2.py")

set(GUI_MANIFEST "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol_gui.exe.manifest")

set(PYTHON_SOURCES
    "${SETUP_PY_IN}"
    "${VERSION_PY_IN}"
    "${MESYCONTROL_PROTO_IN}"

    "${CMAKE_CURRENT_SOURCE_DIR}/cxfreeze_init.py"

    # mesycontrol
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/app_context.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/app_model.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/basic_model.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/basic_tree_model.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/config_gui.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/config_model.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/config_tree_model.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/config_util.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/config_xml.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/device_profile.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/device_registry.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/device_tableview.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/device_view.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/eventloop_callback.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/future.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/gui_mainwindow.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/gui.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/gui_util.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/hardware_controller.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/hardware_model.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/hardware_tree_model.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/__init__.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/log_view.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/mc_treeview.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/model_util.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/mrc_connection.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/parameter_binding.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/proto.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/qt.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/resources.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/script.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/server_process.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/specialized_device.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/tcp_client.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/util.py"

    # mesycontrol/devices
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/__init__.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mcfd16_profile.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mcfd16.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mhv4_profile.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mhv4.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mscf16_profile.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mscf16.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/stm16_profile.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/stm16.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/device_tableview.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/device_view.py"

    # mesycontrol/ui/*.py
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/connect_dialog.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/dialogs.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/__init__.py"

    # mesycontrol/ui/*.ui
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/connect_dialog.ui"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/device_tableview_settings.ui"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/mainwin.ui"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/mhv4_channel_settings.ui"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/mhv4_channel.ui"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/mhv4_global_settings.ui"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/mscf16_channel_settings.ui"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/mscf16_global_settings.ui"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/mscf16_panel.ui"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/subprogress_widget.ui"
)

configure_file(${SETUP_PY_IN} ${SETUP_PY})
configure_file(${VERSION_PY_IN} ${VERSION_PY})

if (WIN32)
  # On Windows the command line does not work correctly:
  # "C:\<some-path>" becomes "C:<some-path>"
  # Using a relative prefix works and installs under the current binary dir.
  set(DISTUTILS_PREFIX "python-install")
else (WIN32)
  set(DISTUTILS_PREFIX "${CMAKE_BINARY_DIR}/python-install")
endif (WIN32)

# Run the generated distutils setup.py script to build the binaries and install
# into the build directory.
add_custom_command(
    OUTPUT ${STAMP}
    COMMAND ${PYTHON_EXECUTABLE} ${SETUP_PY} install --prefix="${DISTUTILS_PREFIX}"
    COMMAND ${CMAKE_COMMAND} -E touch ${STAMP}
    DEPENDS ${PYTHON_SOURCES} ${QRC_OUT} ${PROTO_PY_OUT})

add_custom_command(
    OUTPUT ${QRC_OUT}
    COMMAND ${PYRCC} ${QRC_IN} -o ${QRC_OUT} 
    DEPENDS ${QRC_IN})

add_custom_command(
    OUTPUT ${PROTO_PY_OUT}
    COMMAND ${PROTOBUF_PROTOC_EXECUTABLE}
            -I ${PROTOBUF_IMPORT_DIRS}
            --python_out="${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/"
            "${MESYCONTROL_PROTO_IN}"
    DEPENDS ${MESYCONTROL_PROTO_IN})

add_custom_target(mesycontrol_clients ALL DEPENDS ${STAMP} ${QRC_IN})

# Installation rules for the files generated by distutils.
if (WIN32)
    install(DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/python-install/" DESTINATION bin)
    install(FILES ${GUI_MANIFEST} DESTINATION bin)
else (WIN32)
    install(DIRECTORY ${CMAKE_BINARY_DIR}/python-install/bin/
	    DESTINATION bin USE_SOURCE_PERMISSIONS)
    install(DIRECTORY ${CMAKE_BINARY_DIR}/python-install/lib/
	    DESTINATION lib USE_SOURCE_PERMISSIONS
    PATTERN "*mesycontrol_gui"
        PERMISSIONS OWNER_EXECUTE OWNER_WRITE OWNER_READ
                GROUP_EXECUTE GROUP_READ
            WORLD_EXECUTE WORLD_READ
#    PATTERN "*mesycontrol_script_runner"
#        PERMISSIONS OWNER_EXECUTE OWNER_WRITE OWNER_READ
#                GROUP_EXECUTE GROUP_READ
#            WORLD_EXECUTE WORLD_READ)
    )
endif (WIN32)

# vim:tw=0
