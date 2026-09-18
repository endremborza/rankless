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
    interfacing::{Getters, RootColumns, SubfieldProfiles},
    AttributeLabelUnion,
};

use crate::consts::N_SUBFIELDS;
use crate::responses::{EntityPeersResp, PeerEntry, PeerSubfieldInfo, RefSubfieldInfo};
use crate::state::{start_year, yearly_papers, NameState, StatesT};
use crate::util::{cache_header, get_empty, resolve_entity};

pub(crate) async fn peers_get(
    Path((etype, sem_id)): Path<(String, String)>,
    states: StatesT,
) -> (HeaderMap, Response) {
    peers_inner(&etype, &sem_id, &states)
}

fn peers_inner(etype: &str, sem_id: &str, states: &StatesT) -> (HeaderMap, Response) {
    let gets = &states.2.state.gets;
    // Peers are ranked over the subfield profiles, so a root type without them has no peers view.
    let Some((cols, sfs)) = gets
        .columns_for(etype)
        .and_then(|c| c.subfields.as_ref().map(|s| (c, s)))
    else {
        return get_empty();
    };
    let Some((astates, hero_dm, hero_rid)) = resolve_entity(&states.0 .0, etype, sem_id) else {
        return get_empty();
    };
    let satts = &states.0 .1;

    let sf_atts = &satts[Subfields::NAME];
    let sf_row = sfs.citing.row(hero_dm);
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

    let ref_row = sfs.refed.row(hero_dm);
    let ref_subfields: Vec<RefSubfieldInfo> = (0..N_SUBFIELDS)
        .filter(|&si| ref_row[si] > 0)
        .map(|si| RefSubfieldInfo {
            semantic_id: sf_atts[si].semantic_id.clone(),
            papers: ref_row[si],
        })
        .collect();

    let entry = |rid: usize, dm: usize| {
        build_peer_entry(etype, rid, dm, astates, cols, gets, sfs, satts, &sf_indices)
    };
    let hero = entry(hero_rid, hero_dm);

    let peers: Vec<PeerEntry> = cols.peers[hero_dm]
        .iter()
        .filter(|&&pid| pid != 0)
        .filter_map(|&pid| {
            let peer_dm = pid as usize;
            astates
                .response_id_from_dm(peer_dm)
                .map(|rid| entry(rid, peer_dm))
        })
        .collect();

    let resp = EntityPeersResp {
        top_subfields,
        ref_subfields,
        peers,
        hero,
    };
    (cache_header(60), Json(resp).into_response())
}

#[allow(clippy::too_many_arguments)]
fn build_peer_entry(
    etype: &str,
    rid: usize,
    dm_id: usize,
    astates: &NameState,
    cols: &RootColumns,
    gets: &Getters,
    sfs: &SubfieldProfiles,
    satts: &AttributeLabelUnion,
    sf_indices: &[usize],
) -> PeerEntry {
    let sr = &astates.responses[rid];
    let sf_cits: Vec<u32> = sf_indices
        .iter()
        .map(|&si| sfs.citing.elem(dm_id, si))
        .collect();
    let country = cols.aff_countries.as_ref().and_then(|m| {
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
        yearly_papers: yearly_papers(cols, dm_id),
        yearly_cites: cols.yearly_cites[dm_id],
        start_year: start_year(etype, dm_id, cols, gets),
        h_index: cols.h_indices.as_ref().and_then(|h| h.get(dm_id).copied()),
        year_centroid: cols
            .year_centroids
            .as_ref()
            .and_then(|y| y.get(dm_id).copied()),
        country,
    }
}
