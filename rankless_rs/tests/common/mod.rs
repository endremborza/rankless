pub mod synthetic_oa;

use std::{
    fs::{create_dir_all, remove_dir_all},
    path::PathBuf,
    sync::atomic::{AtomicUsize, Ordering},
};

/// A per-test scratch directory, removed on drop.
pub struct TempRoot(pub PathBuf);

impl TempRoot {
    pub fn new(tag: &str) -> Self {
        static SEQ: AtomicUsize = AtomicUsize::new(0);
        let dir = std::env::temp_dir().join(format!(
            "rankless-{tag}-{}-{}",
            std::process::id(),
            SEQ.fetch_add(1, Ordering::Relaxed)
        ));
        create_dir_all(&dir).unwrap();
        Self(dir)
    }
}

impl Drop for TempRoot {
    fn drop(&mut self) {
        let _ = remove_dir_all(&self.0);
    }
}
