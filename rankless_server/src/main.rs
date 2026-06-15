#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

mod consts;
mod handlers;
mod responses;
mod search_cache;
mod startup;
mod state;
mod util;

use std::{net::SocketAddr, sync::Arc, thread::sleep, time};

use axum::{routing::get, Router};
use socket2::{Domain, Socket, Type};
use tokio::{net::TcpListener, sync::Notify};

use rankless_rs::Stowage;

use crate::consts::{DEFAULT_N_THREADS, PORT};
use crate::handlers::{
    ladder_get, name_get, orcid_get, paper_profile, peers_get, resolve_author_get,
    resolve_work_get, sem_id_get, shallows_get, slice_get, stats_get, tops_get, tree_get, view_get,
    works_get,
};
use crate::startup::get_rest;
use crate::state::NameStateMap;
use crate::util::static_router;

fn main() {
    let n_threads: usize = std::env::var("RANKLESS_THREAD_COUNT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(DEFAULT_N_THREADS);

    tokio::runtime::Builder::new_multi_thread()
        .worker_threads(n_threads)
        .enable_all()
        .build()
        .unwrap()
        .block_on(async_main(n_threads));
}

async fn async_main(n_threads: usize) {
    let shutdown = Arc::new(Notify::new());
    let shutdown_clone = shutdown.clone();
    let signal_task = tokio::spawn(async move {
        tokio::signal::ctrl_c().await.unwrap();
        shutdown_clone.notify_one();
    });

    let path: String = std::env::args().last().unwrap();
    let now = std::time::Instant::now();
    println!("threads: {n_threads} path: {path}");
    let stowage = Stowage::new(&path);
    let (ns_map, satts, tree_manager, counts_response, tops, peer_aux) =
        get_rest(stowage, n_threads);
    let ns_map_arc: Arc<NameStateMap> = ns_map.into();

    let response_api = Router::new()
        .route("/names/:etype", get(name_get))
        .route("/slice/:etype/:from/:to", get(slice_get))
        .route("/views/:etype/:semantic_id", get(view_get))
        .route("/stats/:etype/:semantic_id", get(stats_get))
        .route("/sem-id-via-oa/:etype/:oa_id", get(sem_id_get))
        .route("/orcid/:orcid_id", get(orcid_get))
        .route("/resolve/work", get(resolve_work_get))
        .route("/resolve/author", get(resolve_author_get))
        .route("/paper-profile/:asem", get(paper_profile))
        .route("/peers/:etype/:semantic_id", get(peers_get))
        .route("/ladder/:etype", get(ladder_get))
        .route("/trees/:root_type/:semantic_id", get(tree_get))
        .route("/shallows/:root_type", get(shallows_get))
        .route("/works/:etype/:semantic_id/:from", get(works_get))
        .with_state((ns_map_arc, satts, tree_manager.clone(), peer_aux));

    let count_api = static_router(&counts_response);
    let specs_api = static_router(&tree_manager.specs);

    let tops_api = Router::new()
        .route("/", get(tops_get))
        .with_state(Arc::new(tops));

    let api = Router::new()
        .nest("/", response_api)
        .nest("/counts", count_api)
        .nest("/tops", tops_api)
        .nest("/specs", specs_api);

    let app = Router::new().nest("/v1", api);
    let loc_addr = SocketAddr::from(([127, 0, 0, 1], PORT));
    let stime = now.elapsed().as_secs();
    println!(
        "{loc_addr} set-up in {stime}s ({}min {}sec) - shd",
        stime / 60,
        stime % 60
    );
    let socket = Socket::new(Domain::IPV4, Type::STREAM, None).unwrap();
    socket.set_reuse_address(true).unwrap();
    socket.set_nonblocking(true).unwrap();
    loop {
        match socket.bind(&loc_addr.into()) {
            Ok(_) => break,
            Err(e) => {
                println!("error binding socket: {e}");
                sleep(time::Duration::from_secs(6));
            }
        }
    }
    socket.listen(1024).unwrap();
    let listener = TcpListener::from_std(socket.into()).unwrap();
    axum::serve(listener, app.into_make_service())
        .with_graceful_shutdown(async move {
            shutdown.notified().await;
        })
        .await
        .unwrap();
    signal_task.await.unwrap();
}
