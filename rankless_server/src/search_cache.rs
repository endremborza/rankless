use std::{fs, path::PathBuf};

use muwo_search::SearchEngine;

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

pub(crate) fn try_load_engine<const S: usize>(
    bin_path: &PathBuf,
    stamp_path: &PathBuf,
    key: u64,
) -> Option<SearchEngine<S>> {
    let raw = fs::read(stamp_path).ok()?;
    let stamp_key = u64::from_ne_bytes(raw.try_into().ok()?);
    if stamp_key != key {
        let _ = fs::remove_file(bin_path);
        let _ = fs::remove_file(stamp_path);
        return None;
    }
    let mut file = fs::File::open(bin_path).ok()?;
    SearchEngine::try_load(&mut file)
}

pub(crate) fn save_engine<const S: usize>(
    engine: &SearchEngine<S>,
    bin_path: &PathBuf,
    stamp_path: &PathBuf,
    cache_dir: &PathBuf,
    key: u64,
) {
    if let Err(e) = fs::create_dir_all(cache_dir) {
        println!("search cache: could not create dir: {e}");
        return;
    }
    let result = (|| -> std::io::Result<()> {
        engine.save(&mut fs::File::create(bin_path)?)?;
        fs::write(stamp_path, key.to_ne_bytes())
    })();
    if let Err(e) = result {
        println!("search cache: write failed: {e}");
        let _ = fs::remove_file(bin_path);
        let _ = fs::remove_file(stamp_path);
    }
}
