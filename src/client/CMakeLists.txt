find_package(Python3)
find_package(Protobuf REQUIRED)

set(STAMP         "${CMAKE_CURRENT_BINARY_DIR}/build/timestamp")

# Note: The resources file is updated directly inside the source tree before
# being included in the cx_freeze library.zip by running setup.py.
find_program(PYRCC "pyside2-rcc")
#set(PYRCC       "pyside2-rcc")
set(QRC_IN      "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/resources.qrc")
set(QRC_OUT     "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/resources.py")

set(PROTO_PY_OUT "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/mesycontrol_pb2.py")

#set(GUI_MANIFEST "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol_gui.exe.manifest")
set(GUI_BATCH_STARTER "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol_gui.bat")

set(PYTHON_SOURCES
    "${VERSION_PY_IN}"
    "${MESYCONTROL_PROTO_IN}"

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
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/future.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/gui_mainwindow.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/gui.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/gui_util.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/hardware_controller.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/hardware_model.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/hardware_tree_model.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/hardware_util.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/__init__.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/log_view.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/mc_treeview.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/mesycontrol_pb2.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/model_util.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/mrc_connection.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/parameter_binding.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/proto.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/qt.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/resources.py"
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
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mpd4_profile.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mpd4.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mpd8_profile.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mpd8.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mprb16dr_profile.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mprb16dr.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mprb16_profile.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mprb16.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mscf16_profile.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mscf16.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mux16_profile.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/mux16.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/stm16_profile.py"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/devices/stm16.py"

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
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/mhv4_v20_channel.ui"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/mhv4_v20_settings.ui"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/mscf16_settings.ui"
    "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/ui/subprogress_widget.ui"
)

# Note: for some reason pyside2-rcc is not included in the msys2 pyside2
# package (or the "tools" variant). As the generated resources.py is included
# in the git repo I made the command optional.
if (${PYRCC})
    add_custom_command(
        OUTPUT ${QRC_OUT}
        COMMAND ${PYRCC} ${QRC_IN} -o ${QRC_OUT}
        DEPENDS ${QRC_IN})
endif()

# Generate protobuf python code
add_custom_command(
    OUTPUT ${PROTO_PY_OUT}
    COMMAND ${PROTOBUF_PROTOC_EXECUTABLE}
            -I ${PROTOBUF_IMPORT_DIRS}
            --python_out="${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/"
            "${MESYCONTROL_PROTO_IN}"
    DEPENDS ${MESYCONTROL_PROTO_IN})

find_program(PYINSTALLER_EXECUTABLE pyinstaller REQUIRED)

# Run pyinstaller
add_custom_command(
    OUTPUT ${STAMP}
    COMMAND ${PYINSTALLER_EXECUTABLE} -y ${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol_gui.spec
    COMMAND ${CMAKE_COMMAND} -E touch ${STAMP}
    DEPENDS ${PYTHON_SOURCES} ${VERSION_PY} ${QRC_OUT} ${PROTO_PY_OUT})

add_custom_target(mesycontrol_clients ALL DEPENDS ${STAMP} ${QRC_IN})

install(DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/dist/mesycontrol_gui/"
    DESTINATION bin USE_SOURCE_PERMISSIONS)

install(DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/dist/mesycontrol_script_runner/"
    DESTINATION bin USE_SOURCE_PERMISSIONS)

# vim:tw=0
