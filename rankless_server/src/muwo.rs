use std::{ffi::c_void, io, os::unix::ffi::OsStrExt, path::Path, ptr::NonNull, sync::Once};

use wiretypes::wire;

/// The muwo C ABI this binding speaks; `make muwo-install` refuses a library that speaks another.
#[wire]
pub const ABI: u32 = 1;

pub(crate) struct SearchEngine(NonNull<c_void>);

#[repr(C)]
struct Bytes {
    ptr: *const u8,
    len: usize,
}

impl SearchEngine {
    pub fn new(haystacks: &[String]) -> Self {
        check_library();
        let raw: Vec<Bytes> = haystacks.iter().map(|h| h.as_bytes().into()).collect();
        let engine = unsafe { muwo_build(raw.as_ptr(), raw.len()) };
        Self(NonNull::new(engine).expect("muwo_build returned no engine"))
    }

    pub fn try_load(path: &Path) -> Option<Self> {
        check_library();
        NonNull::new(unsafe { muwo_load(path.into()) }).map(Self)
    }

    pub fn save(&self, path: &Path) -> io::Result<()> {
        match unsafe { muwo_save(self.0.as_ptr(), path.into()) } {
            0 => Ok(()),
            code if code > 0 => Err(io::Error::from_raw_os_error(code)),
            _ => Err(io::Error::other("muwo could not write the index")),
        }
    }

    pub fn query(&self, query: &str) -> Vec<u32> {
        let mut out = Vec::with_capacity(result_size());
        unsafe {
            let n = muwo_query(self.0.as_ptr(), query.as_bytes().into(), out.as_mut_ptr());
            out.set_len(n);
        }
        out
    }
}

impl Drop for SearchEngine {
    fn drop(&mut self) {
        unsafe { muwo_free(self.0.as_ptr()) }
    }
}

// The engine is immutable once built: a query only reads it.
unsafe impl Send for SearchEngine {}
unsafe impl Sync for SearchEngine {}

impl From<&[u8]> for Bytes {
    fn from(b: &[u8]) -> Self {
        Self {
            ptr: b.as_ptr(),
            len: b.len(),
        }
    }
}

impl From<&Path> for Bytes {
    fn from(p: &Path) -> Self {
        p.as_os_str().as_bytes().into()
    }
}

pub(crate) fn result_size() -> usize {
    unsafe { muwo_size() }
}

fn check_library() {
    static CHECKED: Once = Once::new();
    CHECKED.call_once(|| {
        let abi = unsafe { muwo_abi() };
        assert_eq!(abi, ABI, "libmuwo speaks ABI {abi}, rankless-server {ABI}");
        let version = unsafe { muwo_version() };
        let version = unsafe { std::slice::from_raw_parts(version.ptr, version.len) };
        println!("search library: muwo {}", String::from_utf8_lossy(version));
    });
}

#[link(name = "muwo")]
extern "C" {
    fn muwo_abi() -> u32;
    fn muwo_size() -> usize;
    fn muwo_version() -> Bytes;
    fn muwo_build(haystacks: *const Bytes, n: usize) -> *mut c_void;
    fn muwo_query(engine: *const c_void, query: Bytes, out: *mut u32) -> usize;
    fn muwo_save(engine: *const c_void, path: Bytes) -> i32;
    fn muwo_load(path: Bytes) -> *mut c_void;
    fn muwo_free(engine: *mut c_void);
}
