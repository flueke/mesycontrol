find_package(PythonInterp REQUIRED)

set(SETUP_PY_IN "${CMAKE_CURRENT_SOURCE_DIR}/setup.py.in")
set(SETUP_PY    "${CMAKE_CURRENT_BINARY_DIR}/setup.py")
set(STAMP       "${CMAKE_CURRENT_BINARY_DIR}/build/timestamp")

set(PYTHON_SOURCES
   "${CMAKE_CURRENT_SOURCE_DIR}/cxfreeze_ConsoleSetLibPath.py"
   "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol_cli.py"
   "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/device_config.py"
   "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/device_config_xml.py"
   "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/device_desc_mhv4.py"
   "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/device_description.py"
   "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol_gui.py"
   "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/__init__.py"
   "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/protocol.py"
   "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol.py"
   "${SETUP_PY_IN}"
)

configure_file(${SETUP_PY_IN} ${SETUP_PY})

add_custom_command(OUTPUT ${STAMP}
   #COMMAND ${PYTHON_EXECUTABLE} ${SETUP_PY} build
   COMMAND ${PYTHON_EXECUTABLE} ${SETUP_PY} install --prefix "${CMAKE_BINARY_DIR}/python"
   COMMAND ${CMAKE_COMMAND} -E touch ${STAMP}
   DEPENDS ${PYTHON_SOURCES})

add_custom_target(mesycontrol_clients ALL DEPENDS ${STAMP})

install(DIRECTORY ${CMAKE_BINARY_DIR}/python/bin/ DESTINATION bin USE_SOURCE_PERMISSIONS)
install(DIRECTORY ${CMAKE_BINARY_DIR}/python/lib/ DESTINATION lib USE_SOURCE_PERMISSIONS)

# vim:tw=0
