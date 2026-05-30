cmake_minimum_required(VERSION 3.21)

project(
    flowscribe_engine
    VERSION 0.1.0
    DESCRIPTION "Native persistent whisper.cpp engine for FlowScribe"
    LANGUAGES CXX
)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(WHISPER_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
add_subdirectory(third_party/whisper.cpp)

add_executable(
    flowscribe-engine
    src/main.cpp
    src/core/engine_service.cpp
    src/core/job_manager.cpp
    src/core/outbound_dispatcher.cpp
    src/core/scheduler.cpp
    src/core/worker_pool.cpp
    src/ipc/named_pipe_connection.cpp
    src/ipc/named_pipe_server.cpp
    src/protocol/codec.cpp
    src/transcription/chunk_planner.cpp
    src/transcription/chunked_transcription_executor.cpp
    src/transcription/runtime_pool.cpp
    src/transcription/transcript_assembler.cpp
    src/transcription/whisper_runtime.cpp
    third_party/whisper.cpp/examples/common-whisper.cpp
)

target_include_directories(
    flowscribe-engine
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${CMAKE_CURRENT_SOURCE_DIR}/third_party/whisper.cpp/examples
        ${CMAKE_CURRENT_SOURCE_DIR}/third_party/whisper.cpp/include
)

target_link_libraries(flowscribe-engine PRIVATE whisper)

if(MSVC)
    target_compile_options(flowscribe-engine PRIVATE /W4 /permissive-)
else()
    target_compile_options(flowscribe-engine PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_executable(
    flowscribe-engine-protocol-tests
    tests/protocol_tests.cpp
    src/protocol/codec.cpp
    src/transcription/chunk_planner.cpp
    src/transcription/runtime_pool.cpp
    src/transcription/transcript_assembler.cpp
    src/transcription/whisper_runtime.cpp
    third_party/whisper.cpp/examples/common-whisper.cpp
)

target_include_directories(
    flowscribe-engine-protocol-tests
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${CMAKE_CURRENT_SOURCE_DIR}/third_party/whisper.cpp/examples
        ${CMAKE_CURRENT_SOURCE_DIR}/third_party/whisper.cpp/include
)

target_link_libraries(flowscribe-engine-protocol-tests PRIVATE whisper)

if(MSVC)
    target_compile_options(flowscribe-engine-protocol-tests PRIVATE /W4 /permissive-)
else()
    target_compile_options(flowscribe-engine-protocol-tests PRIVATE -Wall -Wextra -Wpedantic)
endif()
