//! Print the final certification report: `cargo run -p final_certification_report --example report`.

fn main() {
    match final_certification_report::generate() {
        Ok(report) => print!("{}", report.render()),
        Err(e) => {
            eprintln!("report generation failed: {e}");
            std::process::exit(1);
        }
    }
}
