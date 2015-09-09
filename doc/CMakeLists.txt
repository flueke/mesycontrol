# generate documentation using the sphinx system
find_package(Sphinx)

if (WIN32)
	message("FIXME: skipping documentation build on windows")
else(WIN32)
if (SPHINX_FOUND)
  find_package(PythonInterp REQUIRED)

  set(SPHINX_SOURCE_DIR "${CMAKE_CURRENT_BINARY_DIR}/sphinx-source")
  set(SPHINX_BUILD_DIR  "${CMAKE_CURRENT_BINARY_DIR}/sphinx-build")
  set(SPHINX_CACHE_DIR  "${CMAKE_CURRENT_BINARY_DIR}/sphinx-cache")
  set(SPHINX_HTML_DIR   "${CMAKE_CURRENT_BINARY_DIR}/sphinx-html")
  set(SPHINX_LATEX_DIR  "${CMAKE_CURRENT_BINARY_DIR}/sphinx-latex")

  # Copy the conf.py.in template and replace parameters.
  configure_file("${CMAKE_CURRENT_SOURCE_DIR}/sphinx/conf.py.in" "${SPHINX_SOURCE_DIR}/conf.py" @ONLY)

  # Build the docs in HTML and PDF format.
  # First the sphinx source directory is copied from the source tree into the
  # build directory. This is needed as sphinx only accepts one `source'
  # directory and the auto-generated API documentation should not be created
  # inside the source tree but rather in the build directory.
  #
  # Second sphinx-apidoc is used to auto generate python API documentation.
  # Then sphinx-build is used to generate the output.
  #
  # Then sphinx is run twice, once for HTML and once for latex output. To
  # generate the final PDF file from the latex sources a final make invocation
  # is needed.
  add_custom_target(doc ALL
    COMMAND
    ${CMAKE_COMMAND}
    -E copy_directory
    "${CMAKE_CURRENT_SOURCE_DIR}/sphinx"
    "${SPHINX_SOURCE_DIR}"

    COMMAND
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

    COMMAND
    ${SPHINX_EXECUTABLE}
    -q -b latex
    -d "${SPHINX_CACHE_DIR}"
    "${SPHINX_SOURCE_DIR}"
    "${SPHINX_LATEX_DIR}"

    COMMAND
    make -C ${SPHINX_LATEX_DIR} all-pdf

    COMMENT "Building documentation with Sphinx"
  )

  install(DIRECTORY "${SPHINX_HTML_DIR}/" DESTINATION "share/doc/html")
  install(FILES "${SPHINX_LATEX_DIR}/mesycontrol.pdf" DESTINATION "share/doc")
else()
  message("Sphinx not found, documentation will not be generated!")
endif()
endif(WIN32)

# vim:tw=0
