use std::process::Command;

const COMMIT_HASH_LEN: usize = include!("src/commit_hash_len.in");

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
}
