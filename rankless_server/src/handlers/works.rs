use std::{cmp::min, sync::Arc};

use axum::{
    extract::{Path, Query},
    http::HeaderMap,
    response::{IntoResponse, Response},
    Json,
};
use hashbrown::{HashMap, HashSet};

use dmove::{
    reverse_prefixed_n, ByteArrayInterface, Entity, EntityMutableMapperBackend, UnsignedNumber,
    VattReadingArcMap, ET,
};
use rankless_rs::{
    gen::{
        a1_entity_mapping::{Authors, Institutions, Sources, Topics},
        a2_init_atts::{DiscardedAuthorsNames, WorkBiblios, WorkDois},
        derive_links3::HitPapers,
    },
    steps::a1_entity_mapping::YearInterface,
};
use rankless_trees::{
    interfacing::Getters,
    io::{EntityAttsForLinks, ManFileHandle, WT},
    path_finder::{extend_with_once_removed, get_direct_links},
    AttributeLabelUnion,
};

use crate::consts::WORKS_PAGE_SIZE_MAX;
use crate::responses::{
    PaginatedPaperSetResp, PaperAuthorMeta, PaperAuthorship, PaperOut, PaperProfileResp,
    PaperSetResp,
};
use crate::state::{InstTrm, StatesT};
use crate::util::{cache_header, get_empty, parse_semantic_id};

pub(crate) async fn works_get(
    Path((etype, sem_id, pstart)): Path<(String, String, usize)>,
    Query(wq): Query<crate::responses::WorksQ>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let page_size = wq.n.unwrap_or(WORKS_PAGE_SIZE_MAX).min(WORKS_PAGE_SIZE_MAX);
    if let Some(state) = states.0 .0.get(etype.as_str()) {
        let psid = parse_semantic_id(sem_id);
        if let Some(&dm_id) = state.semantic_id_map.get(psid.as_str()) {
            if let Some(work_arr) = states
                .0
                 .2
                .state
                .gets
                .works_of_entity(dm_id as usize, etype)
            {
                if !work_arr.is_empty() {
                    let start = min(pstart, work_arr.len() - 1);
                    let wids = work_arr[start..].iter().take(page_size).map(WT::to_usize);
                    let resp = get_paper_set_resp(wids, states.2.clone());
                    let out = PaginatedPaperSetResp {
                        resp,
                        total_papers: work_arr.len(),
                        slice_start: start,
                    };
                    return (cache_header(60), Json(out).into_response());
                }
            }
        }
    }
    get_empty()
}

pub(crate) async fn paper_profile(
    Path(author_sem_id): Path<String>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let astates = states.0 .0.get(Authors::NAME).unwrap();
    let gets = &states.0 .2.state.gets;
    let Some(&aid_dm) = astates.semantic_id_map.get(author_sem_id.as_str()) else {
        return get_empty();
    };
    let aid = aid_dm as usize;
    let Some(aid_rid) = astates.response_id_from_dm(aid) else {
        return get_empty();
    };
    let hw_set: HashSet<WT> = astates.exts[aid_rid]
        .hit_papers
        .iter()
        .map(|hwid| gets.hit_papers[hwid.to_usize()])
        .collect();

    let direct_hit_wids: Vec<WT> = gets
        .author_citing_direct(aid)
        .iter()
        .map(|&hid| gets.hit_papers[hid as usize] as WT)
        .collect();
    let once_hit_wids: Vec<WT> = gets
        .author_citing_once(aid)
        .iter()
        .map(|&hid| gets.hit_papers[hid as usize] as WT)
        .collect();

    let refed_wids: &[WT] = gets.aworks(ET::<Authors>::from_usize(aid));
    let refed_set: HashSet<WT> = refed_wids.iter().copied().collect();

    let mut conn = get_direct_links(gets, refed_set.clone(), &direct_hit_wids);
    extend_with_once_removed(gets, refed_set, &once_hit_wids, &mut conn);

    let wids = hw_set
        .iter()
        .chain(conn.wids.iter().filter(|wid| !hw_set.contains(*wid)))
        .map(|e| e.to_usize());

    let papers = get_paper_set_resp(wids, states.2.clone());
    let out = PaperProfileResp {
        dag: conn.dag,
        papers,
    };
    (cache_header(60), Json(out).into_response())
}

fn get_paper_set_resp<I>(wids: I, trm: Arc<InstTrm>) -> PaperSetResp
where
    I: Iterator<Item = usize>,
{
    let mut disc_author_names = HashMap::new();
    let mut authors_meta = HashMap::new();
    let mut wnames_handle = trm.get_file_handle();
    let mut doi_hand = trm.get_file_handle();
    let mut dan_hand = trm.get_file_handle();

    let mut entity_atts: EntityAttsForLinks = HashMap::new();
    let papers = wids
        .map(|wid| {
            paper_out(
                wid.to_usize(),
                &trm.state.gets,
                &mut wnames_handle,
                &mut doi_hand,
                &mut dan_hand,
                &mut disc_author_names,
                &mut authors_meta,
                &mut entity_atts,
                &trm.state.att_union,
            )
        })
        .collect();
    PaperSetResp {
        papers,
        entity_atts,
        disc_author_names,
        authors_meta,
    }
}

fn paper_out(
    wid: usize,
    gets: &Getters,
    wname_handler: &mut ManFileHandle,
    doi_handler: &mut VattReadingArcMap<WorkDois>,
    disc_name_handler: &mut VattReadingArcMap<DiscardedAuthorsNames>,
    discarded_author_name_map: &mut HashMap<String, String>,
    authors_meta: &mut HashMap<usize, PaperAuthorMeta>,
    entity_atts: &mut EntityAttsForLinks,
    att_union: &AttributeLabelUnion,
) -> PaperOut {
    let mut yearly_cites = None;
    let mut is_hit = false;
    let mut hit_bm = None;
    let mut hit_sem_id = None;
    let mut created_topic = None;
    let (name, doi) = if let (Some(hwid), Some(hit_attlu)) = (
        gets.hit_wid_map.get(&WT::from_usize(wid)),
        att_union.get(HitPapers::NAME),
    ) {
        let hit_atts = &hit_attlu[*hwid];
        let name = hit_atts.name.to_string();
        hit_sem_id = Some(hit_atts.semantic_id.to_string());
        let ct = gets.hit_created_topic(hwid).to_usize();
        if ct != 0 {
            created_topic = att_union
                .get(Topics::NAME)
                .and_then(|labels| labels.get(ct))
                .map(|label| label.name.to_string());
        }
        let doi = if hit_atts.semantic_id.starts_with("W") {
            hit_atts.semantic_id.to_string()
        } else {
            String::new()
        };
        yearly_cites = Some(gets.hit_yearlies(*hwid).into());
        hit_bm = Some(gets.hit_bms(hwid).to_usize() as u32);
        is_hit = true;
        (name, doi)
    } else {
        let name = wname_handler
            .get_via_mut(&wid)
            .unwrap_or("Unknown".to_string());
        let doi = doi_handler.get_via_mut(&wid).unwrap_or("".to_string());
        (name, doi)
    };
    let mut add_to_eatts = |etype: &str, k: usize| {
        if let Some(u_eatts) = att_union.get(etype) {
            let eatts = entity_atts
                .entry(etype.to_string())
                .or_insert_with(HashMap::new);
            if eatts.contains_key(&k) {
                return;
            };
            if let Some(v) = u_eatts.get(k) {
                eatts.insert(k, v.clone());
            }
        }
    };
    //this is similarly to String with hit paper names not automatically remakes
    //the var sized element from &[SubType]
    let biblio = Some(<ET<WorkBiblios> as ByteArrayInterface>::from_bytes(
        gets.wbiblios(wid),
    ));
    let mut positioned_ships: Vec<(usize, PaperAuthorship)> = Vec::new();
    for anyship in gets.wanyships(wid) {
        let (is_filterd, ship_id) = reverse_prefixed_n(anyship.to_usize());
        let (full_aid, insts_slice, position) = if is_filterd {
            let aid = gets.fshipa(&ship_id);
            add_to_eatts(Authors::NAME, aid.to_usize());
            let prize_rec = gets.author_prizes(aid);
            authors_meta.insert(
                aid.to_usize(),
                PaperAuthorMeta {
                    prize: prize_rec.0,
                    year: YearInterface::reverse(prize_rec.1),
                },
            );
            let pos = gets.fship_pos(&ship_id).to_usize();
            (format!("F{aid}"), gets.fshipis(ship_id), pos)
        } else {
            let aid = gets.dshipa(&ship_id);
            let name = disc_name_handler
                .get_via_mut(&aid.to_usize())
                .unwrap_or("Unknown".to_string());
            let full_aid = format!("D{aid}");
            discarded_author_name_map.insert(full_aid.clone(), name);
            let pos = gets.dship_pos(&ship_id).to_usize();
            (full_aid, gets.dshipis(ship_id), pos)
        };
        let mut insts = Vec::new();
        for iid in insts_slice {
            add_to_eatts(Institutions::NAME, iid.to_usize());
            insts.push(iid.to_usize());
        }
        positioned_ships.push((
            position,
            PaperAuthorship {
                author: full_aid,
                insts,
            },
        ));
    }
    positioned_ships.sort_by_key(|(p, _)| *p);
    let authorships: Vec<PaperAuthorship> = positioned_ships.into_iter().map(|(_, a)| a).collect();
    let source = gets.top_source(&wid).to_usize();
    add_to_eatts(Sources::NAME, source);

    PaperOut {
        wid,
        oa_id: gets.work_oa.get(wid).copied().unwrap_or(0),
        year: YearInterface::reverse(*gets.year(&wid)),
        name,
        hit_sem_id,
        doi,
        citations: gets.wccount(wid) as u32,
        yearly_cites,
        biblio,
        source,
        authorships,
        is_hit,
        hit_bm,
        created_topic,
    }
}
