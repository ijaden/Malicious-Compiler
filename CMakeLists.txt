cmake_minimum_required(VERSION 3.16)
project(galois_ot_wrapper)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_compile_options(
    -fcoroutines
    -pthread
    -march=native
    -maes
    -mpclmul
    -Wno-deprecated-declarations
)

add_definitions(-DMACORO_CPP_20=1)
set(LIBOTE_INSTALL "${CMAKE_CURRENT_SOURCE_DIR}/libOTe/out/install/linux")
include_directories(SYSTEM
    "${LIBOTE_INSTALL}/include"
)
link_directories(
    "${LIBOTE_INSTALL}/lib"
)
add_library(galois_ot SHARED GaloisOT.cpp)
set_target_properties(galois_ot PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_link_libraries(galois_ot PRIVATE
    libOTe
    cryptoTools
    coproto
    macoro
    boost_system
    pthread
)