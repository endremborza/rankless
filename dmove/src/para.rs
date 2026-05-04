use std::{
    sync::{Arc, Condvar, Mutex, MutexGuard},
    thread::available_parallelism,
};

use crossbeam_channel::{bounded, Receiver};

pub type AcTuple<T> = Arc<(Mutex<T>, Condvar)>;

pub trait Worker<T>
where
    T: Send,
    Self: Sized + Sync,
{
    const CAPACITY_PER_THREAD: usize = 100;

    fn proc(&self, input: T);

    fn post(self) -> Self {
        self
    }

    fn para<I>(self, in_v: I) -> Self
    where
        I: Iterator<Item = T>,
    {
        let n_threads: usize = std::thread::available_parallelism().unwrap().into();
        self.para_n(in_v, n_threads)
    }
    fn para_n<I>(self, in_v: I, n: usize) -> Self
    where
        I: Iterator<Item = T>,
    {
        para_run::<Self, T, _>(in_v, &self, n);
        self.post()
    }
}

#[macro_export]
macro_rules! par_join {
    ($($f:expr),+ $(,)?) => {{
        std::thread::scope(|s| {
            let handles = [$( s.spawn($f) ),+];
            handles.map(|h| h.join().expect("thread panicked"))
        })
    }};
}

#[macro_export]
macro_rules! para_multi_gen_run {
    ($fun: ident, $($t: ident),*; $parc: expr) => {
        {
            let mut threads = Vec::new();
            $(
                let pc = $parc.clone();
                threads.push(
                    std::thread::spawn(move || $fun::<$t>(&pc))
                );
            )*
            threads.into_iter().map(|t| t.join().unwrap())
        }
    };
}

pub fn set_and_notify<T>(cvp: AcTuple<T>, val: T) {
    let (lock, cvar) = &*cvp;
    let mut data = lock.lock().unwrap();
    *data = val;
    cvar.notify_all();
}

pub fn wait_for_data<T>(cvp: AcTuple<Option<T>>) -> T {
    wait_for_data_with_taker(cvp, |mut x| x.take().unwrap())
}

pub fn wait_for_data_copy<T>(cvp: AcTuple<Option<T>>) -> T
where
    T: Copy,
{
    wait_for_data_with_taker(cvp, |x| *x.as_ref().unwrap())
}

pub fn wait_for_data_with_taker<T, F>(cvp: AcTuple<Option<T>>, taker: F) -> T
where
    for<'a> F: FnOnce(MutexGuard<'a, Option<T>>) -> T,
{
    let (lock, cvar) = &*cvp;
    let mut data = lock.lock().unwrap();
    while data.is_none() {
        data = cvar.wait(data).unwrap();
    }
    taker(data)
}

pub fn map_reduce<T, Acc, MapFn, ReduceFn, I>(
    it: I,
    inner_fn: MapFn,
    mut reduce_fn: ReduceFn,
    n_threads: Option<usize>,
) -> Acc
where
    T: Send + 'static,
    I: Iterator<Item = T>,
    Acc: Default + Send + 'static,
    MapFn: Fn(&mut Acc, T) + Send + Sync + 'static,
    ReduceFn: FnMut(&mut Acc, Acc),
{
    let n_threads: usize = n_threads.unwrap_or(available_parallelism().unwrap().into());
    let inner_fn = Arc::new(inner_fn);
    let (sender, r) = bounded(n_threads * 2);

    let accs: Vec<Acc> = std::thread::scope(|s| {
        let mut threads_v = Vec::new();
        for _ in 0..n_threads {
            let inner_fn = inner_fn.clone();
            let in_clone = r.clone();
            threads_v.push(s.spawn(move || {
                let mut new_acc = Acc::default();
                subf(in_clone, |e| inner_fn(&mut new_acc, e));
                new_acc
            }));
        }

        for e in it {
            sender.send(Some(e)).unwrap();
        }
        for _ in 0..(n_threads) {
            sender.send(None).unwrap();
        }

        threads_v
            .into_iter()
            .map(|t| t.join().expect("thread failed"))
            .collect()
    });

    let mut result = Acc::default();
    for res in accs {
        reduce_fn(&mut result, res);
    }
    result
}

fn para_run<W, T, I>(in_v: I, setup: &W, n_threads: usize)
where
    W: Worker<T> + Sync,
    I: Iterator<Item = T>,
    T: Send,
{
    let capacity = n_threads * W::CAPACITY_PER_THREAD;
    let (sender, r) = bounded(capacity);

    std::thread::scope(|s| {
        let mut threads_v = Vec::new();
        for _ in 0..(n_threads) {
            let in_clone = r.clone();
            threads_v.push(s.spawn(move || subf(in_clone, |e| setup.proc(e))));
        }

        for e in in_v {
            sender.send(Some(e)).unwrap();
        }
        for _ in 0..(n_threads) {
            sender.send(None).unwrap();
        }
        for t in threads_v.into_iter() {
            t.join().expect("thread failed");
        }
    });
}

fn subf<F, T>(r: Receiver<Option<T>>, mut f: F)
where
    F: FnMut(T),
    T: Send,
{
    loop {
        if let Some(qc_in) = r.recv().unwrap() {
            f(qc_in);
        } else {
            break;
        };
    }
}
