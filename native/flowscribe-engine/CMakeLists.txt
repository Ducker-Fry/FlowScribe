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

add_executable(
    flowscribe-engine
    src/main.cpp
)

target_include_directories(
    flowscribe-engine
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

if(MSVC)
    target_compile_options(flowscribe-engine PRIVATE /W4 /permissive-)
else()
    target_compile_options(flowscribe-engine PRIVATE -Wall -Wextra -Wpedantic)
endif()

