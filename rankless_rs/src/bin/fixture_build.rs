//! `fixture-build <dir>`: the synthetic minimal OpenAlex snapshot under `<dir>/snapshot`
//! (`to-csv` reads `<dir>/snapshot/data`) plus `<dir>/scenario.json` naming every id the
//! ledger flow can act on. The generator is the integration tests' own; see
//! `tests/common/synthetic_oa.rs`.

use std::{fs::File, io, path::Path};

#[allow(dead_code)]
#[path = "../../tests/common/synthetic_oa.rs"]
mod synthetic_oa;

use synthetic_oa::Scenario;

fn main() -> io::Result<()> {
    let dir = std::env::args()
        .nth(1)
        .expect("usage: fixture-build <out_dir>");
    let out = Path::new(&dir);
    let scenario = Scenario::new();
    scenario.write_snapshot(&out.join("snapshot"))?;
    serde_json::to_writer_pretty(File::create(out.join("scenario.json"))?, &scenario)?;
    println!(
        "{} works, {} authors → {}",
        scenario.works.len(),
        scenario.persons().count(),
        out.display()
    );
    Ok(())
}
