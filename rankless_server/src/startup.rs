use std::sync::{Arc, Mutex};

use hashbrown::HashMap;

use dmove::{
    para::{set_and_notify, wait_for_data_copy, AcTuple},
    para_multi_gen_run, Entity, NamespacedEntity,
};
use rankless_rs::{
    common::MainEntity,
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        derive_links3::HitPapers,
    },
    steps::a1_entity_mapping::Qs,
    Stowage,
};
use rankless_trees::{
    extensions::DistinctionText,
    interfacing::{
        make_stats_entry_arc, Getters, NodeInterfaceable, NodeInterfaces, PeerAuxMap,
        RootInterfaceable, RootInterfaces,
    },
    io::TreeRunManager,
    AttributeLabelUnion,
};

use crate::responses::{CountsResponse, EntityDescription, TopResult};
use crate::state::{InstTrm, IsTop, NameState, NameStateMap};

type StateKv = (&'static str, (NameState, TopResult, EntityDescription));

pub(crate) fn get_rest(
    stowage: Stowage,
    n_threads: usize,
) -> (
    NameStateMap,
    Arc<AttributeLabelUnion>,
    Arc<InstTrm>,
    CountsResponse,
    Vec<TopResult>,
    Arc<PeerAuxMap>,
) {
    let gets = Arc::new(Getters::new(Arc::new(stowage)));
    let mux_satts: Arc<Mutex<AttributeLabelUnion>> = Arc::new(Mutex::new(HashMap::new()));
    let cv_pair = AcTuple::<Option<f64>>::default();
    let mut ns_map: NameStateMap = HashMap::new();
    let mut tops = Vec::new();
    let peer_aux = {
        let m = gets.build_peer_aux();
        print_mem_use("loaded peer aux");
        Arc::new(m)
    };
    let counts_response = {
        let mut descriptions = Vec::new();
        print_mem_use("pre thread starts");
        let arg_tup = (gets.clone(), mux_satts.clone(), cv_pair.clone());
        let ei_ns_kvs = para_multi_gen_run!(get_state_tr_ed_kv, Institutions, Authors, Subfields, Countries, Sources, HitPapers; arg_tup);
        let ccount = gets.total_cite_count();
        set_and_notify(cv_pair, Some(ccount));
        let arg_tup_n = (gets.clone(), mux_satts.clone(), ccount.clone());
        para_multi_gen_run!(update_w_node_if, Topics, Qs; arg_tup_n).last();
        for (name, (nstate, tr, ed)) in ei_ns_kvs {
            tops.push(tr);
            descriptions.push(ed);
            ns_map.insert(name, nstate);
        }
        CountsResponse {
            entities: descriptions,
            total_citations: ccount as u64,
            total_works: Works::N,
        }
    };
    print_mem_use("after ei ns map");
    let satts = Arc::into_inner(mux_satts).unwrap().into_inner().unwrap();
    let asatts = Arc::new(satts);
    let tm: Arc<InstTrm> = TreeRunManager::new(gets, asatts.clone(), n_threads);
    print_mem_use("got tm");
    (ns_map, asatts, tm, counts_response, tops, peer_aux)
}

fn print_mem_use(suff: &str) {
    if let Ok(status) = std::fs::read_to_string("/proc/self/status") {
        for line in status.lines() {
            if line.starts_with("VmRSS:") {
                println!("Memory usage at {suff}: {line}");
                break;
            }
        }
    }
}

fn update_w_node_if<T>(
    (gets, mux_satts, ccount): &(Arc<Getters>, Arc<Mutex<AttributeLabelUnion>>, f64),
) where
    T: NodeInterfaceable,
{
    let (k, v) = NodeInterfaces::<T>::new(&gets.stowage).into_stats_entry(*ccount);
    mux_satts.lock().unwrap().insert(k, v);
}

fn get_state_tr_ed_kv<E>(
    full_tup: &(
        Arc<Getters>,
        Arc<Mutex<AttributeLabelUnion>>,
        AcTuple<Option<f64>>,
    ),
) -> StateKv
where
    E: RootInterfaceable + IsTop + MainEntity + NamespacedEntity + DistinctionText,
{
    let (gets_clone, au_clone, shared_cvp) = full_tup.clone();
    let name = E::NAME.to_string();
    let ent_intf = RootInterfaces::<E>::new(&gets_clone.stowage);
    let names_arc: Box<[Arc<str>]> = (&ent_intf.names).into();
    let sem_ids_arc: Box<[Arc<str>]> = (&ent_intf.sem_ids).into();
    let nstate = NameState::new::<E>(&ent_intf, &gets_clone, &names_arc, &sem_ids_arc);
    let ccount = wait_for_data_copy(shared_cvp);
    let (k, v) = make_stats_entry_arc::<E>(&names_arc, &sem_ids_arc, &ent_intf.ccounts, ccount);
    au_clone.lock().unwrap().insert(k, v);
    let entities = nstate
        .responses
        .iter()
        .filter(|e| <E as IsTop>::is_top(e))
        .map(|e| e.clone())
        .collect();
    let tr = TopResult { name, entities };
    let ed = EntityDescription::new::<E>(nstate.responses.len());
    (E::NAME, (nstate, tr, ed))
}
