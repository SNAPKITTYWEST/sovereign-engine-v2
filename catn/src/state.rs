use tenferro_tensor::{Tensor, DType};
use tenferro_gpu::cuda::{CudaBackend, CudaDevice};

/// Cellular / tensor-network state for one CATN cell or block.
/// All tensors live on the CUDA device via tenferro device management.
#[derive(Debug)]
pub struct CellularState {
    /// Local state tensor (MPS/PEPS core or density-like block).
    /// Stored in tenferro column-major native layout.
    pub state: Tensor,
    /// Neighborhood bond tensors (incoming / outgoing).
    pub neighborhood: Vec<Tensor>,
    /// Active bond dimensions after truncation (max 64).
    pub chi: Vec<usize>,
    pub device: CudaDevice,
}

impl CellularState {
    /// Allocate all tensors explicitly on the CUDA device.
    pub fn new_on_cuda(
        backend:     &mut CudaBackend,
        shape:       &[usize],
        n_neighbors: usize,
        dtype:       DType,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        let device = CudaDevice::default()?;
        let state  = Tensor::zeros(shape, dtype, &device, backend)?;

        let mut neighborhood = Vec::with_capacity(n_neighbors);
        for _ in 0..n_neighbors {
            neighborhood.push(Tensor::zeros(&[64, 64], dtype, &device, backend)?);
        }

        Ok(Self {
            state,
            neighborhood,
            chi:    vec![64; n_neighbors],
            device,
        })
    }

    /// Accept a row-major host buffer (e.g. from PyTorch convention) and
    /// materialize a column-major tenferro tensor on CUDA.
    /// Uses a strided view when possible; falls back to an explicit transpose copy.
    pub fn from_row_major_host(
        backend:       &mut CudaBackend,
        row_major_data: &[f32],
        shape:         &[usize],
        device:        &CudaDevice,
    ) -> Result<Tensor, Box<dyn std::error::Error>> {
        let host      = Tensor::from_vec_row_major(shape.to_vec(), row_major_data.to_vec())?;
        let gpu       = host.to_device(device, backend)?;
        let col_major = gpu.to_column_major(backend)?;
        Ok(col_major)
    }
}
