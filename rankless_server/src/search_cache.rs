use std::{
    fs,
    io::{BufWriter, Write},
    path::{Path, PathBuf},
};

use crate::consts::HAYSTACKS_DIR_VAR;
use crate::muwo::SearchEngine;

pub(crate) fn fnv64(iter: impl Iterator<Item = impl AsRef<[u8]>>) -> u64 {
    const BASIS: u64 = 0xcbf29ce484222325;
    const PRIME: u64 = 0x00000100000001b3;
    let mut h = BASIS;
    for chunk in iter {
        for &b in chunk.as_ref() {
            h ^= b as u64;
            h = h.wrapping_mul(PRIME);
        }
    }
    h
}

pub(crate) fn try_load_engine(
    bin_path: &PathBuf,
    stamp_path: &PathBuf,
    key: u64,
) -> Option<SearchEngine> {
    let raw = fs::read(stamp_path).ok()?;
    let stamp_key = u64::from_ne_bytes(raw.try_into().ok()?);
    if stamp_key != key {
        let _ = fs::remove_file(bin_path);
        let _ = fs::remove_file(stamp_path);
        return None;
    }
    SearchEngine::try_load(bin_path)
}

pub(crate) fn save_engine(
    engine: &SearchEngine,
    bin_path: &PathBuf,
    stamp_path: &PathBuf,
    cache_dir: &PathBuf,
    key: u64,
) {
    if let Err(e) = fs::create_dir_all(cache_dir) {
        println!("search cache: could not create dir: {e}");
        return;
    }
    let result = engine
        .save(bin_path)
        .and_then(|()| fs::write(stamp_path, key.to_ne_bytes()));
    if let Err(e) = result {
        println!("search cache: write failed: {e}");
        let _ = fs::remove_file(bin_path);
        let _ = fs::remove_file(stamp_path);
    }
}

pub(crate) fn haystacks_dir() -> Option<PathBuf> {
    std::env::var_os(HAYSTACKS_DIR_VAR).map(PathBuf::from)
}

pub(crate) fn export_haystacks(dir: &Path, etype: &str, haystacks: &[String]) {
    let path = dir.join(format!("{etype}.txt"));
    let result = (|| -> std::io::Result<()> {
        fs::create_dir_all(dir)?;
        let mut w = BufWriter::new(fs::File::create(&path)?);
        for haystack in haystacks {
            // the tokenizer skips a line break, so dropping it keeps the haystack's words
            writeln!(w, "{}", haystack.replace('\n', ""))?;
        }
        w.flush()
    })();
    result.unwrap_or_else(|e| panic!("writing {}: {e}", path.display()));
}
