cmake_minimum_required(VERSION 3.24)
project(sovereign-ide C CXX)

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT WIN32)
    message(FATAL_ERROR "Sovereign IDE targets Windows only (Win32 + Direct2D)")
endif()

add_compile_definitions(_WIN32_WINNT=0x0A00 NTDDI_VERSION=0x0A000000)

if(MSVC)
    add_compile_options(/W4 /WX /utf-8)
else()
    add_compile_options(-Wall -Wextra -Werror -Wno-missing-field-initializers)
endif()

# --- Core library (pure C, no GUI deps) ---
add_library(sov_core STATIC
    native/core/arena.c
    native/core/strings.c
    native/core/events.c
    native/editor/buffer.c
    native/editor/document.c
    native/chat/protocol.c
    native/fcl/evaluator.c
    native/git/repository.c
    native/build/cmake_runner.c
    native/lsp/client.c
)
target_include_directories(sov_core PUBLIC native)

# --- Editor graphics (C++, Direct2D + DirectWrite) ---
add_library(sov_editor STATIC
    native/graphics/d2d_renderer.cpp
    native/editor/editor_view.cpp
)
target_include_directories(sov_editor PUBLIC native)
target_link_libraries(sov_editor PUBLIC sov_core d2d1 dwrite dxgi ole32)

# --- UI widgets (C++, Direct2D + DirectWrite) ---
add_library(sov_ui STATIC
    native/ui/layout.c
    native/ui/project_tree.cpp
    native/ui/status_bar.cpp
    native/ui/output_panel.cpp
    native/terminal/conpty.c
    native/terminal/terminal_view.cpp
)
target_include_directories(sov_ui PUBLIC native)
target_link_libraries(sov_ui PUBLIC sov_core sov_editor d2d1 dwrite ole32)

# --- Platform layer (C, Win32) ---
add_library(sov_platform STATIC
    native/platform/windows/application.c
    native/platform/windows/shell.c
    native/chat/pipe_client.c
)
target_include_directories(sov_platform PUBLIC native)
target_link_libraries(sov_platform PUBLIC sov_core sov_editor sov_ui user32 gdi32 shcore comdlg32 shell32)

# --- Main executable ---
add_executable(sovereign-ide WIN32 native/main.c)
target_link_libraries(sovereign-ide PRIVATE sov_core sov_platform sov_editor sov_ui)
if(MINGW)
    target_link_options(sovereign-ide PRIVATE -municode -static-libgcc -static-libstdc++ -static)
endif()

set_target_properties(sovereign-ide PROPERTIES
    OUTPUT_NAME "sovereign-ide"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

# --- Tests ---
enable_testing()

add_executable(test_core
    tests/test_arena.c
    tests/test_strings.c
    tests/test_events.c
    tests/test_buffer.c
    tests/test_protocol.c
    tests/test_fcl.c
    tests/test_main.c
)
target_link_libraries(test_core PRIVATE sov_core)
target_include_directories(test_core PRIVATE native)

add_test(NAME core_tests COMMAND test_core)
