use std::{env, fs, ops::AddAssign, path::Path};

// The env the workspace is built for. Make exports it from the repo-root .env; a bare cargo
// or rust-analyzer invocation has it unset, so the same .env is the fallback — otherwise the
// two disagree and each rewrite of env_consts.rs rebuilds every downstream crate.
fn dotenv_rankless_env() -> Option<String> {
    let text = fs::read_to_string(Path::new("..").join(".env")).ok()?;
    text.lines()
        .filter_map(|l| l.split_once('='))
        .filter(|(k, _)| k.trim() == "RANKLESS_ENV")
        .map(|(_, v)| v.trim().trim_matches('"').to_owned())
        .last()
}

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=../.env");
    println!("cargo:rerun-if-env-changed=RANKLESS_ENV");
    let path = Path::new("src").join("env_consts.rs");

    let rankless_env = env::var("RANKLESS_ENV")
        .ok()
        .filter(|e| !e.is_empty())
        .or_else(dotenv_rankless_env)
        .unwrap_or_else(|| "full".to_owned());
    let envs = vec!["nano", "micro", "mini"];

    let mut e_ind = 0;
    for e in envs.iter() {
        if *e == rankless_env {
            break;
        }
        e_ind.add_assign(1);
    }

    let years = [("FINAL_YEAR", 2026), ("START_YEAR", 1950)];
    // The pipeline's thresholds per env; `#[wire]` hands the env's own to the site and the MCP
    // server, so their generated files differ per env like this one.
    let thresholds = [
        ("MIN_PAPERS_FOR_INST", [40, 20, 30, 250]),
        ("MIN_PAPERS_FOR_SOURCE", [10, 20, 50, 200]),
        ("MIN_AUTHOR_WORK_COUNT", [10, 10, 10, 8]),
        ("MIN_AUTHOR_CITE_COUNT", [500, 500, 500, 400]),
        // ("MIN_AUTHOR_H_INDEX", [3, 3, 3, 5]),
        // ("MIN_AUTHOR_I10_INDEX", [2, 2, 2, 3]),
    ];

    let mut env_lines = vec!["use wiretypes::wire;\n".to_string()];
    for (name, value) in years {
        env_lines.push(format!("pub const {name}: u16 = {value};"));
    }
    for (name, values) in thresholds {
        env_lines.push(format!(
            "#[wire]\npub const {name}: u16 = {};",
            values[e_ind]
        ));
    }
    env_lines.push(format!(
        "pub const RANKLESS_ENV: &str = \"{rankless_env}\";"
    ));
    let new_content = env_lines.join("\n") + "\n";
    if fs::read_to_string(&path).unwrap_or_default() != new_content {
        fs::write(&path, new_content).unwrap();
    }
}
