cmake_minimum_required(VERSION 3.18)
project(drain_pipeline_cuda LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CUDA_STANDARD 17)

find_package(CUDAToolkit REQUIRED)

add_executable(cuda_pipeline
    cuda_pipeline.cu
    load_checkpoint.cpp
)

target_compile_options(cuda_pipeline PRIVATE
    $<$<COMPILE_LANGUAGE:CUDA>:-O3 --use_fast_math>
)

target_link_libraries(cuda_pipeline PRIVATE CUDA::cudart)
