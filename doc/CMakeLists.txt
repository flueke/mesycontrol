# generate documentation using the sphinx system
find_package(Sphinx)

if (SPHINX_FOUND)
  set(SPHINX_SOURCE_DIR "${CMAKE_CURRENT_BINARY_DIR}/sphinx-source")
  set(SPHINX_BUILD_DIR  "${CMAKE_CURRENT_BINARY_DIR}/sphinx-build")
  set(SPHINX_CACHE_DIR  "${CMAKE_CURRENT_BINARY_DIR}/sphinx-cache")
  set(SPHINX_HTML_DIR   "${CMAKE_CURRENT_BINARY_DIR}/sphinx-html")
  set(SPHINX_LATEX_DIR  "${CMAKE_CURRENT_BINARY_DIR}/sphinx-latex")

  # Copy the sphinx source directory from the source tree to the build
  # directory, skipping only the config file template. This is needed as sphinx
  # only accepts one `source' directory and the auto-generated API
  # documentation should not be created inside the source tree but rather in
  # the build directory.
  # FIXME: this copy operation is only done at cmake invocation time, not at
  # the time make runs.
  #file(COPY "${CMAKE_CURRENT_SOURCE_DIR}/sphinx/"
  #  DESTINATION "${SPHINX_SOURCE_DIR}"
  #  PATTERN "conf.py.in" EXCLUDE)

  add_custom_command(TARGET mesycontrol_html_docs PRE_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory "${CMAKE_CURRENT_SOURCE_DIR}/sphinx" "${SPHINX_SOURCE_DIR}")

  # Copy the conf.py.in template and replace parameters.
  configure_file("${CMAKE_CURRENT_SOURCE_DIR}/sphinx/conf.py.in" "${SPHINX_SOURCE_DIR}/conf.py" @ONLY)

  # Build the docs in HTML format.
  # First sphinx-apidoc is used to auto generate python API documentation. Then
  # sphinx-build is used to generate the output.
  add_custom_target(mesycontrol_html_docs ALL
    sphinx-apidoc
    -f -d 2
    -o "${SPHINX_SOURCE_DIR}"
    "${CMAKE_SOURCE_DIR}/src/client/mesycontrol"      # package dir
    "${CMAKE_SOURCE_DIR}/src/client/mesycontrol/test" # exclude
    "${CMAKE_SOURCE_DIR}/src/client/mesycontrol/ui"   # exclude

    COMMAND
    ${SPHINX_EXECUTABLE}
    -q -b html
    -d "${SPHINX_CACHE_DIR}"
    "${SPHINX_SOURCE_DIR}"
    "${SPHINX_HTML_DIR}"
    COMMENT "Building HTML documentation with Sphinx")

  # Build the docs in PDF format.
  add_custom_target(mesycontrol_pdf_docs ALL
    sphinx-apidoc
    -f -d 2
    -o "${SPHINX_SOURCE_DIR}"
    "${CMAKE_SOURCE_DIR}/src/client/mesycontrol"      # package dir
    "${CMAKE_SOURCE_DIR}/src/client/mesycontrol/test" # exclude
    "${CMAKE_SOURCE_DIR}/src/client/mesycontrol/ui"   # exclude

    COMMAND
    ${SPHINX_EXECUTABLE}
    -q -b latex
    -d "${SPHINX_CACHE_DIR}"
    "${SPHINX_SOURCE_DIR}"
    "${SPHINX_LATEX_DIR}"

    COMMAND
    make -C ${SPHINX_LATEX_DIR} all-pdf
    COMMENT "Building PDF documentation with Sphinx")

  install(DIRECTORY "${SPHINX_HTML_DIR}/" DESTINATION "share/doc/html")
  install(FILES "${SPHINX_LATEX_DIR}/mesycontrol.pdf" DESTINATION "share/doc")

endif()

#FIND_PACKAGE(Doxygen)
#IF(DOXYGEN_FOUND)
#  SET(doxyfile_in          ${CMAKE_CURRENT_SOURCE_DIR}/Doxyfile.in     )
#  SET(doxyfile             ${PROJECT_BINARY_DIR}/Doxyfile              )
#  SET(doxy_html_index_file ${CMAKE_CURRENT_BINARY_DIR}/html/index.html )
#  SET(doxy_output_root     ${CMAKE_CURRENT_BINARY_DIR}                 ) # Pasted into Doxyfile.in
#  SET(doxy_input           ${PROJECT_SOURCE_DIR}/src                   ) # Pasted into Doxyfile.in
#  SET(doxy_extra_files
#     ${CMAKE_CURRENT_SOURCE_DIR}/mainpage.dox 
#     )
#
#  CONFIGURE_FILE( ${doxyfile_in} ${doxyfile} @ONLY )
#
#  ADD_CUSTOM_COMMAND( OUTPUT ${doxy_html_index_file}
#                      COMMAND ${DOXYGEN_EXECUTABLE} ${doxyfile}
#                      # The following should be ${doxyfile} only but it
#                      # will break the dependency.
#                      # The optimal solution would be creating a
#                      # custom_command for ${doxyfile} generation
#                      # but I still have to figure out how...
#                      MAIN_DEPENDENCY ${doxyfile} ${doxyfile_in}
#                      DEPENDS ${SERVER_TARGET} ${CLIENT_TARGET} ${doxy_extra_files}
#                      COMMENT "Generating HTML documentation")
#
#  ADD_CUSTOM_TARGET(doc ALL DEPENDS ${doxy_html_index_file})
#
#  INSTALL(DIRECTORY
#     ${CMAKE_CURRENT_BINARY_DIR}/html
#     DESTINATION share/doc/${CMAKE_PROJECT_NAME})
#
#  INSTALL(FILES
#     ${CMAKE_CURRENT_SOURCE_DIR}/index.html
#     ${doxy_extra_files}
#     DESTINATION share/doc/${CMAKE_PROJECT_NAME})
#ENDIF()


# vim:tw=0
