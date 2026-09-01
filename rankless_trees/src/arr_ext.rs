const SOURCE_BUF_SIZE: usize = 0x200;
const TARGET_BUF_SIZE: usize = 0x500;

struct StackWExtension<const L: usize, T> {
    buf: [T; L],
    blen: usize,
    vec: Vec<T>,
}

impl<const L: usize, T> StackWExtension<L, T>
where
    T: Default + Copy + Clone,
{
    fn new() -> Self {
        Self {
            buf: [T::default(); L],
            vec: Vec::new(),
            blen: 0,
        }
    }

    fn reset(&mut self) {
        unsafe { self.vec.set_len(0) }
        self.blen = 0;
    }

    fn get(&self, ind: usize) -> &T {
        if ind >= self.buf.len() {
            &self.vec[ind - self.blen]
        } else {
            &self.buf[ind]
        }
    }

    fn len(&self) -> usize {
        self.blen + self.vec.len()
    }
}

impl<T, const L: usize> ExtendableArr<T> for StackWExtension<L, T> {
    fn add(&mut self, e: T) {
        if self.blen == self.buf.len() {
            self.vec.push(e)
        } else {
            self.buf[self.blen] = e;
            self.blen += 1;
        }
    }
}
