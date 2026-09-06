mod dispatcher;
mod kernels;
mod state;

use dispatcher::CatnDispatcher;
use state::CellularState;
use tenferro_tensor::DType;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let shape   = &[64usize, 64];
    let steps   = 10;
    let output  = run_catn_loop(steps, shape)?;
    println!("CATN complete. Final chi: {:?}", output.chi);
    Ok(())
}

fn run_catn_loop(
    steps: usize,
    shape: &[usize],
) -> Result<dispatcher::CatnOutput, Box<dyn std::error::Error>> {
    let mut dispatcher = CatnDispatcher::new()?;
    let mut cell = CellularState::new_on_cuda(
        &mut dispatcher.backend,
        shape,
        /* n_neighbors */ 4,
        DType::F32,
    )?;

    for _ in 0..steps {
        dispatcher.step(&mut cell)?;
    }

    Ok(dispatcher.export(&cell))
}
