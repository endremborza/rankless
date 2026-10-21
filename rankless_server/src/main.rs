#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

mod cohort;
mod consts;
mod handlers;
mod responses;
mod routes;
mod search_cache;
mod startup;
mod state;
mod util;

use std::{net::SocketAddr, sync::Arc, thread::sleep, time};

use axum::{extract::State, routing::get, Router};
use socket2::{Domain, Socket, Type};
use tokio::{net::TcpListener, sync::Notify};

use rankless_rs::Stowage;

use crate::consts::{DEFAULT_N_THREADS, PORT, TREES_ONLY_FLAG};
use crate::handlers::{column_registry, tops_get};
use crate::routes::{nested_routes, server_routes, tree_routes, API_PREFIX};
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

    let args: Vec<String> = std::env::args().collect();
    let path = args.last().unwrap().clone();
    let trees_only = args.iter().any(|a| a == TREES_ONLY_FLAG);
    let now = std::time::Instant::now();
    println!("threads: {n_threads} path: {path} trees only: {trees_only}");
    let stowage = Stowage::new(&path);
    let (ns_map, satts, tree_manager, counts_response, tops, server) =
        get_rest(stowage, n_threads, trees_only);
    let ns_map_arc: Arc<NameStateMap> = ns_map.into();
    let states = State((ns_map_arc, satts, tree_manager.clone()));
    let columns_api = static_router(&column_registry(&states));

    let tree_api = tree_routes().with_state(states.0.clone());
    let response_api = match server {
        None => tree_api,
        Some(server) => {
            let (ns_map, satts, trm) = states.0;
            tree_api.merge(server_routes().with_state((ns_map, satts, trm, server)))
        }
    };

    let count_api = static_router(&counts_response);
    let specs_api = static_router(&serde_json::json!({ "version": util::version_stamp(&path) }));

    let tops_api = Router::new()
        .route("/", get(tops_get))
        .with_state(Arc::new(tops));

    let api = Router::new().nest("/", response_api).merge(nested_routes(
        count_api,
        columns_api,
        tops_api,
        specs_api,
    ));

    let app = Router::new().nest(API_PREFIX, api);
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

#[cfg(test)]
mod wire_types {
    // The one test binary that links every crate with `#[wire]` types.
    #[test]
    fn generated_types_are_current() {
        if let Err(e) = wiretypes::sync(concat!(env!("CARGO_MANIFEST_DIR"), "/../wiretypes.toml")) {
            panic!("{e}");
        }
    }
}
