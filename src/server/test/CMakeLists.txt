if (Boost_UNIT_TEST_FRAMEWORK_FOUND)
  set(TEST_TARGET "test_runner")
  set(TEST_SRCS
    ../logging.cc
    #../mrc1_connection.cc
    ../mrc1_reply_parser.cc
    #../mrc1_request_queue.cc
    ../protocol.cc
    #../tcp_connection.cc
    #../tcp_connection.cc
    #../tcp_connection_manager.cc
    #../tcp_server.cc
    test_mrc1_reply_parser.cc
    )
  include_directories(${CMAKE_CURRENT_SOURCE_DIR}/..)
  add_executable(${TEST_TARGET} EXCLUDE_FROM_ALL ${TEST_SRCS} )
  target_link_libraries(${TEST_TARGET} ${Boost_LIBRARIES})

  if(WIN32)
      # Statically link against the GCC and C++ libraries to avoid
      # depending on DLLs installed with MinGW.
      set(CMAKE_EXE_LINKER_FLAGS "-static-libgcc -static-libstdc++")
      # Link against the DLLs needed by boost::asio
      set(WINDOWS_LIBS ws2_32 wsock32)
      target_link_libraries(${TEST_TARGET} ${WINDOWS_LIBS})
  else(WIN32)
      target_link_libraries(${TEST_TARGET} rt)
  endif(WIN32)

else (Boost_UNIT_TEST_FRAMEWORK_FOUND)
  message("Boost unit test framework not found. Not building unit tests")
endif (Boost_UNIT_TEST_FRAMEWORK_FOUND)
