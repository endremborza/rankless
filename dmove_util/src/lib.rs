use std::{
    fs::File,
    io::{self, Write},
    process::Command,
};

const RUSTFMT_EDITION: &str = "2021";

pub fn write_rs_file(path: &str, content: &str) -> io::Result<usize> {
    let written = File::create(path)?.write(content.as_bytes())?;
    rustfmt_file(path);
    Ok(written)
}

fn rustfmt_file(path: &str) {
    let status = Command::new("rustfmt")
        .args(["--edition", RUSTFMT_EDITION, path])
        .status()
        .expect("rustfmt (rustup component) required to emit fmt-clean generated code");
    assert!(status.success(), "rustfmt failed on {path}");
}
