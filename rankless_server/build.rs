use std::process::Command;

const COMMIT_HASH_LEN: usize = include!("src/commit_hash_len.in");
const MUWO_LIB_DIR_VAR: &str = "MUWO_LIB_DIR";

fn main() {
    println!("cargo:rerun-if-changed=../.git/HEAD");
    println!("cargo:rerun-if-changed=../.git/refs");
    let hash = Command::new("git")
        .args(["rev-parse", &format!("--short={COMMIT_HASH_LEN}"), "HEAD"])
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_else(|| "unknown".to_string());
    println!("cargo:rustc-env=GIT_COMMIT={hash}");
    link_muwo();
}

// `.cargo/config.toml` sets the variable to an absolute path.
fn link_muwo() {
    println!("cargo:rerun-if-env-changed={MUWO_LIB_DIR_VAR}");
    let dir = std::env::var(MUWO_LIB_DIR_VAR).unwrap_or_else(|e| panic!("{MUWO_LIB_DIR_VAR}: {e}"));
    println!("cargo:rustc-link-search=native={dir}");
    println!("cargo:rustc-link-arg=-Wl,-rpath,{dir}");
}
