use axum::{
    extract::Path,
    http::HeaderMap,
    response::{IntoResponse, Response},
    Json,
};

use dmove::{Entity, UnsignedNumber, ET};
use rankless_rs::{
    gen::a1_entity_mapping::{Countries, Subfields},
    peers::SPEC_BETA,
};
use rankless_trees::{
    interfacing::{PeerAux, TopRels},
    AttributeLabelUnion,
};

use crate::consts::N_SUBFIELDS;
use crate::responses::{EntityPeersResp, PeerEntry, PeerSubfieldInfo};
use crate::state::{NameState, StatesT};
use crate::util::{cache_header, get_empty};

pub(crate) async fn peers_get(
    Path((etype, sem_id)): Path<(String, String)>,
    states: StatesT,
) -> (HeaderMap, Response) {
    peers_inner(&etype, &sem_id, &states)
}

fn peers_inner(etype: &str, sem_id: &str, states: &StatesT) -> (HeaderMap, Response) {
    let (Some(astates), Some(aux)) = (states.0 .0.get(etype), states.0 .3.get(etype)) else {
        return get_empty();
    };
    let satts = &states.0 .1;
    let gets = &states.2.state.gets;
    let top_rels = gets.top_rels_for(etype);

    let Some(&hero_dm) = astates.semantic_id_map.get(sem_id) else {
        return get_empty();
    };
    let hero_dm = hero_dm as usize;
    let Some(hero_rid) = astates.response_id_from_dm(hero_dm) else {
        return get_empty();
    };

    let sf_atts = &satts[Subfields::NAME];
    let sf_row = aux.cit_subfields.row(hero_dm);
    let mut sf_scores: Vec<(usize, f64)> = (0..N_SUBFIELDS)
        .filter(|&si| sf_row[si] > 0)
        .map(|si| {
            (
                si,
                sf_row[si] as f64
                    / (gets.sfworks(si as ET<Subfields>).len() as f64).powf(SPEC_BETA),
            )
        })
        .collect();
    sf_scores.sort_unstable_by(|a, b| b.1.total_cmp(&a.1));
    let sf_indices: Vec<usize> = sf_scores.into_iter().map(|(si, _)| si).collect();

    let top_subfields: Vec<PeerSubfieldInfo> = sf_indices
        .iter()
        .map(|&si| {
            let att = &sf_atts[si];
            PeerSubfieldInfo {
                name: att.name.clone(),
                semantic_id: att.semantic_id.clone(),
                dm_id: si,
            }
        })
        .collect();

    let hero = build_peer_entry(
        hero_rid,
        hero_dm,
        astates,
        aux,
        satts,
        top_rels,
        &sf_indices,
    );

    let peers: Vec<PeerEntry> = astates.peers[hero_dm]
        .iter()
        .filter(|&&pid| pid != 0)
        .filter_map(|&pid| {
            let peer_dm = pid as usize;
            astates.response_id_from_dm(peer_dm).map(|rid| {
                build_peer_entry(rid, peer_dm, astates, aux, satts, top_rels, &sf_indices)
            })
        })
        .collect();

    let resp = EntityPeersResp {
        top_subfields,
        peers,
        hero,
    };
    (cache_header(60), Json(resp).into_response())
}

fn build_peer_entry(
    rid: usize,
    dm_id: usize,
    astates: &NameState,
    aux: &PeerAux,
    satts: &AttributeLabelUnion,
    top_rels: Option<&TopRels>,
    sf_indices: &[usize],
) -> PeerEntry {
    let sr = &astates.responses[rid];
    let ext = &astates.exts[rid];
    let sf_cits: Vec<u32> = sf_indices
        .iter()
        .map(|&si| aux.cit_subfields.elem(dm_id, si))
        .collect();
    let country = top_rels
        .and_then(|tr| tr.aff_countries.as_ref())
        .and_then(|m| {
            m.row(dm_id)
                .into_iter()
                .map(|(_, c)| c.to_usize())
                .find(|&c| c != 0)
                .and_then(|cdm| {
                    satts
                        .get(Countries::NAME)
                        .and_then(|labels| labels.get(cdm))
                        .map(|l| l.name.clone())
                })
        });
    PeerEntry {
        name: sr.name.clone(),
        semantic_id: sr.semantic_id.clone(),
        papers: sr.papers,
        citations: sr.citations,
        subfield_citations: sf_cits,
        yearly_papers: ext.yearly_papers,
        yearly_cites: ext.yearly_cites,
        start_year: ext.start_year,
        h_index: aux.h_indices.as_ref().and_then(|h| h.get(dm_id).copied()),
        year_centroid: aux
            .year_centroids
            .as_ref()
            .and_then(|y| y.get(dm_id).copied()),
        country,
    }
}
