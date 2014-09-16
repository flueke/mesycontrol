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

find_package(Sphinx)

if (SPHINX_FOUND)
  set(SPHINX_BUILD_DIR "${CMAKE_CURRENT_BINARY_DIR}/sphinx-build")
  set(SPHINX_CACHE_DIR "${CMAKE_CURRENT_BINARY_DIR}/sphinx-cache")
  set(SPHINX_HTML_DIR  "${CMAKE_CURRENT_BINARY_DIR}/sphinx-html")
  set(SPHINX_LATEX_DIR "${CMAKE_CURRENT_BINARY_DIR}/sphinx-latex")

  configure_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/sphinx/conf.py.in"
    "${SPHINX_BUILD_DIR}/conf.py"
    @ONLY)

  add_custom_target(mesycontrol_html_docs ALL
    ${SPHINX_EXECUTABLE}
    -q
    -b html
    -c "${SPHINX_BUILD_DIR}"
    -d "${SPHINX_CACHE_DIR}"
    "${CMAKE_CURRENT_SOURCE_DIR}/sphinx"
    "${SPHINX_HTML_DIR}"
    COMMENT "Building HTML documentation with Sphinx")

  add_custom_target(mesycontrol_pdf_docs ALL
    ${SPHINX_EXECUTABLE}
    -q
    -b latex
    -c "${SPHINX_BUILD_DIR}"
    -d "${SPHINX_CACHE_DIR}"
    "${CMAKE_CURRENT_SOURCE_DIR}/sphinx"
    "${SPHINX_LATEX_DIR}"
    COMMAND
    make -C ${SPHINX_LATEX_DIR} all-pdf
    COMMENT "Building PDF documentation with Sphinx")

  install(DIRECTORY "${SPHINX_HTML_DIR}/" DESTINATION "share/doc/html")
  install(FILES "${SPHINX_LATEX_DIR}/mesycontrol.pdf" DESTINATION "share/doc")

endif()
