find_program(PYTHON "python")

if (PYTHON)
   set(SETUP_PY_IN "${CMAKE_CURRENT_SOURCE_DIR}/setup.py.in")
   set(SETUP_PY    "${CMAKE_CURRENT_BINARY_DIR}/setup.py")
   set(DEPS        "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol/__init__.py")
   set(STAMP       "${CMAKE_CURRENT_BINARY_DIR}/build/timestamp")

   configure_file(${SETUP_PY_IN} ${SETUP_PY})

   add_custom_command(OUTPUT ${STAMP}
      COMMAND ${PYTHON} ${SETUP_PY} build
      COMMAND ${PYTHON} ${SETUP_PY} install --prefix "${CMAKE_BINARY_DIR}/python"
      COMMAND ${CMAKE_COMMAND} -E touch ${STAMP}
      DEPENDS ${DEPS})

   add_custom_target(mesycontrol_clients ALL DEPENDS ${STAMP})

   # install(CODE "execute_process(COMMAND ${PYTHON} ${SETUP_PY} install --prefix ${CMAKE_INSTALL_PREFIX})")
   install(DIRECTORY ${CMAKE_BINARY_DIR}/python/bin/ DESTINATION bin USE_SOURCE_PERMISSIONS)
   install(DIRECTORY ${CMAKE_BINARY_DIR}/python/lib/ DESTINATION lib USE_SOURCE_PERMISSIONS)

endif(PYTHON)

# vim:tw=0
