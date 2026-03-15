use std::{env, ops::AddAssign};

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-env-changed=RANKLESS_ENV");
    let path = std::path::Path::new("src").join("env_consts.rs");

    let rankless_env = env::var_os("RANKLESS_ENV").unwrap_or("full".into());
    let envs = vec!["nano", "micro", "mini"];

    let mut e_ind = 0;
    for e in envs.iter() {
        if *e == rankless_env {
            break;
        }
        e_ind.add_assign(1);
    }

    let year = 2026;
    let start_year = 1950;
    let env_dependent_vars = vec![
        ("FINAL_YEAR", [year, year, year, year]),
        (
            "START_YEAR",
            [start_year, start_year, start_year, start_year],
        ),
        ("MIN_PAPERS_FOR_INST", [40, 20, 30, 250]),
        ("MIN_PAPERS_FOR_SOURCE", [10, 20, 50, 200]),
        ("MIN_AUTHOR_WORK_COUNT", [10, 10, 10, 8]),
        ("MIN_AUTHOR_CITE_COUNT", [500, 500, 500, 400]),
        // ("MIN_AUTHOR_H_INDEX", [3, 3, 3, 5]),
        // ("MIN_AUTHOR_I10_INDEX", [2, 2, 2, 3]),
    ];

    let mut env_lines = Vec::new();
    for e_var in env_dependent_vars.iter() {
        env_lines.push(format!("pub const {}: u16 = {};", e_var.0, e_var.1[e_ind]))
    }
    let new_content = env_lines.join("\n");
    if std::fs::read_to_string(&path).unwrap_or_default() != new_content {
        std::fs::write(&path, new_content).unwrap();
    }
}
