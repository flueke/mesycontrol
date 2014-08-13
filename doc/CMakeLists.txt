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
