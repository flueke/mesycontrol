
# Install the pydoc generated api reference.
install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/mesycontrol-py-help.txt" DESTINATION "share/doc/mesycontrol")

# Build Sphinx documentation.
# Source: https://eb2.co/blog/2012/03/sphinx-and-cmake-beautiful-documentation-for-c-projects/

# Notes (flueke):
# * Using different cache directories for each type of build to avoid race
#   conditions when using multiple make jobs.
# * add_custom_command() and add_custom_target() together are used to create a
#   dependency chain for CMake: the command specifies the output, the target
#   depends on the output.
find_package(Sphinx)
find_program(LATEXMK latexmk)

if (SPHINX_EXECUTABLE)

  set(SPHINX_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/sphinx")
  set(SPHINX_BUILD_DIR  "${CMAKE_CURRENT_BINARY_DIR}/sphinx-build")
  set(SPHINX_CACHE_DIR  "${CMAKE_CURRENT_BINARY_DIR}/sphinx-cache")
  set(SPHINX_HTML_DIR   "${CMAKE_CURRENT_BINARY_DIR}/sphinx-html")
  set(SPHINX_LATEX_DIR  "${CMAKE_CURRENT_BINARY_DIR}/sphinx-latex")
  set(SPHINX_PDF_OUT    "${SPHINX_LATEX_DIR}/mesycontrol.pdf")

  # Copies the footer logo for the latex build.
  configure_file(
      "${SPHINX_SOURCE_DIR}/mesytec-logo-yellow.png"
      "${SPHINX_LATEX_DIR}/mesytec-logo-yellow.png"
      COPYONLY
      )

  add_custom_target(mesycontrol_doc ALL)

  # html
  # ==================================================

  configure_file(
      "${SPHINX_SOURCE_DIR}/conf.py.in"
      "${SPHINX_BUILD_DIR}/html/conf.py"
      @ONLY
      )

  add_custom_target(mesycontrol_doc_html
      ${SPHINX_EXECUTABLE}
      -E -b html
      -c "${SPHINX_BUILD_DIR}/html"
      -d "${SPHINX_CACHE_DIR}/html"
      "${SPHINX_SOURCE_DIR}"
      "${SPHINX_HTML_DIR}"
      COMMENT "Building HTML documentation with Sphinx"
      )

  add_dependencies(mesycontrol_doc mesycontrol_doc_html)

  install(DIRECTORY "${SPHINX_HTML_DIR}/" DESTINATION "share/doc/mesycontrol/html" OPTIONAL)

  # latex + pdf
  # ==================================================
  if (LATEXMK)
    configure_file(
        "${SPHINX_SOURCE_DIR}/conf.py.in"
        "${SPHINX_BUILD_DIR}/latex/conf.py"
        @ONLY
        )

    add_custom_target(mesycontrol_doc_latex
      ${SPHINX_EXECUTABLE}
      -E -b latex
      -c "${SPHINX_BUILD_DIR}/latex"
      -d "${SPHINX_CACHE_DIR}/latex"
      "${SPHINX_SOURCE_DIR}"
      "${SPHINX_LATEX_DIR}"
      COMMENT "Building latex documentation with Sphinx"
      )

    add_dependencies(mesycontrol_doc mesycontrol_doc_latex)

    # latex -> pdf
    add_custom_target(mesycontrol_doc_latex_pdf
            make -C ${SPHINX_LATEX_DIR}
            COMMENT "Generating PDF from Sphinx latex output")

    add_dependencies(mesycontrol_doc_latex_pdf mesycontrol_doc_latex)
    add_dependencies(mesycontrol_doc mesycontrol_doc_latex_pdf)

    install(FILES "${SPHINX_PDF_OUT}" DESTINATION "share/doc/mesycontrol" OPTIONAL)

  else(LATEXMK)
    message("-- The latexmk program was not found on your system. Will not generate PDF documentation.")
  endif(LATEXMK)
else()
  message("Sphinx not found, documentation can not be generated.")
endif()

# vim:tw=0
