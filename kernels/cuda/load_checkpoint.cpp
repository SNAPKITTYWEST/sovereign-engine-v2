/*********************************************************************
 * load_checkpoint.cpp
 *
 * Loads a binary checkpoint file into a vector<Tensor>.
 *
 * File format (contiguous blocks, no header required):
 *   | shape (i32) | dtype (i32) | rank (i32) | sparsity (i32) |
 *   | norm  (i32) | param_count (i32) | layer (i32) | role (i32) |
 *********************************************************************/

#include <cstdio>
#include <cstdint>
#include <vector>
#include <fstream>
#include <stdexcept>

/* Must match the layout in cuda_pipeline.cu */
struct Tensor {
    int32_t shape;
    int32_t dtype;
    int32_t rank;
    int32_t sparsity;
    int32_t norm;
    int32_t param_count;
    int32_t layer;
    int32_t role;
};

std::vector<Tensor> load_checkpoint(const char *filename)
{
    std::ifstream in(filename, std::ios::binary);
    if (!in)
        throw std::runtime_error("Could not open checkpoint file");

    in.seekg(0, std::ios::end);
    std::streamsize size = in.tellg();
    in.seekg(0, std::ios::beg);

    if (size % static_cast<std::streamsize>(sizeof(Tensor)) != 0)
        throw std::runtime_error("File size is not a multiple of Tensor size");

    size_t tensor_count = static_cast<size_t>(size) / sizeof(Tensor);
    std::vector<Tensor> tensors(tensor_count);

    if (!in.read(reinterpret_cast<char *>(tensors.data()), size))
        throw std::runtime_error("Failed to read checkpoint data");

    return tensors;
}

int main()
{
    const char *ckpt_path = "model.ckpt";

    std::vector<Tensor> tensors;
    try {
        tensors = load_checkpoint(ckpt_path);
    } catch (const std::exception &e) {
        std::fprintf(stderr, "Error loading checkpoint: %s\n", e.what());
        return EXIT_FAILURE;
    }

    std::printf("Loaded %zu tensors from '%s'\n", tensors.size(), ckpt_path);

    /* Hand off to GPU pipeline:
     * std::vector<Tensor> kept = run_pipeline(tensors);
     */

    return EXIT_SUCCESS;
}
