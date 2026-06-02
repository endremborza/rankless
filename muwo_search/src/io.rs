use std::io;

use super::{
    CustomTrie, FixedHeap, GenTrie, IndType, SearchEngine, TrieLeaf, TrieLeaves, TrieNodeL1,
    TrieNodeRoot, WordViaCharr, CHAR_COUNT,
};

const MAGIC: &[u8; 4] = b"MWS\x01";

impl<const S: usize> SearchEngine<S> {
    pub fn save<W: io::Write>(&self, w: &mut W) -> io::Result<()> {
        w.write_all(MAGIC)?;
        write_u32(w, S as u32)?;
        let ca = &self.tree.char_array;
        write_u64(w, ca.len() as u64)?;
        w.write_all(ca)?;
        save_root(&self.tree.prefix_tree, w)?;
        save_root(&self.tree.inner_tree, w)
    }

    pub fn try_load<R: io::Read>(r: &mut R) -> Option<Self> {
        let mut magic = [0u8; 4];
        r.read_exact(&mut magic).ok()?;
        if magic != *MAGIC {
            return None;
        }
        if read_u32(r)? as usize != S {
            return None;
        }
        let ca_len = read_u64(r)? as usize;
        let mut char_array = vec![0u8; ca_len];
        r.read_exact(&mut char_array).ok()?;
        let prefix_tree = load_root::<S>(r)?;
        let inner_tree = load_root::<S>(r)?;
        Some(Self {
            tree: CustomTrie {
                prefix_tree,
                inner_tree,
                char_array: char_array.into(),
            },
        })
    }
}

fn save_heap<const S: usize>(
    heap: &FixedHeap<IndType, S>,
    w: &mut impl io::Write,
) -> io::Result<()> {
    for &v in heap.arr.iter() {
        write_u32(w, v)?;
    }
    Ok(())
}

fn load_heap<const S: usize>(r: &mut impl io::Read) -> Option<FixedHeap<IndType, S>> {
    let mut arr = [IndType::MAX; S];
    for slot in arr.iter_mut() {
        *slot = read_u32(r)?;
    }
    Some(FixedHeap { arr })
}

fn save_leaves(leaves: &TrieLeaves, w: &mut impl io::Write) -> io::Result<()> {
    write_u32(w, leaves.0.len() as u32)?;
    for leaf in leaves.0.iter() {
        write_u32(w, leaf.suffix.start_idx)?;
        write_u16(w, leaf.suffix.len)?;
        write_u32(w, leaf.ids.len() as u32)?;
        for &id in leaf.ids.iter() {
            write_u32(w, id)?;
        }
    }
    Ok(())
}

fn load_leaves(r: &mut impl io::Read) -> Option<TrieLeaves> {
    let count = read_u32(r)? as usize;
    let mut leaves = Vec::with_capacity(count);
    for _ in 0..count {
        let start_idx = read_u32(r)?;
        let len = read_u16(r)?;
        let id_count = read_u32(r)? as usize;
        let mut ids = Vec::with_capacity(id_count);
        for _ in 0..id_count {
            ids.push(read_u32(r)?);
        }
        leaves.push(TrieLeaf {
            suffix: WordViaCharr { start_idx, len },
            ids: ids.into(),
        });
    }
    Some(TrieLeaves(leaves.into()))
}

fn save_l1<const S: usize>(node: &TrieNodeL1<S>, w: &mut impl io::Write) -> io::Result<()> {
    save_heap(&node.out, w)?;
    for child in node.children.iter() {
        save_leaves(child, w)?;
    }
    Ok(())
}

fn load_l1<const S: usize>(r: &mut impl io::Read) -> Option<TrieNodeL1<S>> {
    let out = load_heap::<S>(r)?;
    let mut cv = Vec::with_capacity(CHAR_COUNT);
    for _ in 0..CHAR_COUNT {
        cv.push(load_leaves(r)?);
    }
    Some(GenTrie {
        out,
        children: cv.try_into().ok()?,
    })
}

fn save_root<const S: usize>(root: &TrieNodeRoot<S>, w: &mut impl io::Write) -> io::Result<()> {
    save_heap(&root.out, w)?;
    for child in root.children.iter() {
        save_l1(child, w)?;
    }
    Ok(())
}

fn load_root<const S: usize>(r: &mut impl io::Read) -> Option<TrieNodeRoot<S>> {
    let out = load_heap::<S>(r)?;
    let mut cv = Vec::with_capacity(CHAR_COUNT);
    for _ in 0..CHAR_COUNT {
        cv.push(load_l1::<S>(r)?);
    }
    Some(GenTrie {
        out,
        children: cv.try_into().ok()?,
    })
}

fn write_u16(w: &mut impl io::Write, v: u16) -> io::Result<()> {
    w.write_all(&v.to_ne_bytes())
}

fn write_u32(w: &mut impl io::Write, v: u32) -> io::Result<()> {
    w.write_all(&v.to_ne_bytes())
}

fn write_u64(w: &mut impl io::Write, v: u64) -> io::Result<()> {
    w.write_all(&v.to_ne_bytes())
}

fn read_u16(r: &mut impl io::Read) -> Option<u16> {
    let mut buf = [0u8; 2];
    r.read_exact(&mut buf).ok()?;
    Some(u16::from_ne_bytes(buf))
}

fn read_u32(r: &mut impl io::Read) -> Option<u32> {
    let mut buf = [0u8; 4];
    r.read_exact(&mut buf).ok()?;
    Some(u32::from_ne_bytes(buf))
}

fn read_u64(r: &mut impl io::Read) -> Option<u64> {
    let mut buf = [0u8; 8];
    r.read_exact(&mut buf).ok()?;
    Some(u64::from_ne_bytes(buf))
}
