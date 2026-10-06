use std::{
    cmp::{min, Reverse},
    sync::Arc,
};

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
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics},
        a2_init_atts::{AuthorshipDiscardedAuthor, DiscardedAuthorsNames, WorkBiblios, WorkDois},
        derive_links3::HitPapers,
    },
    metrics::{decode_bar, paper_score, WORK_SCREEN},
    steps::a1_entity_mapping::YearInterface,
};
use rankless_trees::{
    interfacing::Getters,
    io::{EntityAttsForLinks, ManFileHandle, WT},
    path_finder::{extend_with_once_removed, get_direct_links},
    work_set::cnf_intersect,
    AttributeLabelUnion,
};

use crate::consts::{
    INTERSECT_DEFAULT_N, INTERSECT_MAX_BASE, INTERSECT_MAX_CLAUSES, INTERSECT_MAX_OPERANDS,
    WORKS_PAGE_SIZE_MAX,
};
use crate::responses::{
    PaginatedPaperSetResp, PaperAuthorMeta, PaperAuthorship, PaperOut, PaperProfileResp,
    PaperSetResp,
};
use crate::state::{hit_papers, InstTrm, StatesT};
use crate::util::{bad_text, cache_header, get_empty, resolve_dm, root_cols};

// Entity types whose work-lists may be intersected. Restricted to the five "stat" facets: their
// semantic IDs are slugs containing none of the path separators (`/ , :`), so the catch-all CNF
// encoding stays unambiguous. Hit-papers/citing-works carry `/` in DOIs and aren't meaningful
// facets, so they are excluded.
const INTERSECTABLE: [&str; 5] = [
    Authors::NAME,
    Countries::NAME,
    Institutions::NAME,
    Sources::NAME,
    Subfields::NAME,
];

// One authorship row of a work: `id` indexes the filtered or discarded authorship attributes.
#[derive(Clone, Copy, Debug)]
struct Ship {
    pos: usize,
    author: ShipAuthor,
    id: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ShipAuthor {
    Filtered(ET<Authors>),
    Discarded(ET<AuthorshipDiscardedAuthor>),
}

pub(crate) async fn works_get(
    Path((etype, sem_id, pstart)): Path<(String, String, usize)>,
    Query(wq): Query<crate::responses::WorksQ>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let page_size = wq.n.unwrap_or(WORKS_PAGE_SIZE_MAX).min(WORKS_PAGE_SIZE_MAX);
    let Some((_, dm_id)) = resolve_dm(&states.0 .0, &etype, &sem_id) else {
        return get_empty();
    };
    let requested = (etype == Authors::NAME).then(|| ET::<Authors>::from_usize(dm_id));
    let gets = &states.0 .2.state.gets;
    let Some(work_arr) = gets.works_of_entity(dm_id, etype) else {
        return get_empty();
    };
    if work_arr.is_empty() {
        return get_empty();
    }
    let total = work_arr.len();
    let start = min(pstart, total - 1);
    let rmaker = |a: &[WT]| {
        get_paper_set_resp(
            a[start..].iter().take(page_size),
            requested.as_slice(),
            states.2.clone(),
        )
    };
    let resp = if wq.sort.as_deref() == Some("citations") {
        let mut sorted = work_arr.to_vec();
        sorted.sort_by_key(|&w| Reverse(gets.wccount(w.to_usize())));
        rmaker(&sorted)
    } else {
        rmaker(work_arr)
    };
    let out = PaginatedPaperSetResp {
        resp,
        total_papers: total,
        slice_start: start,
    };
    (cache_header(60), Json(out).into_response())
}

// Intersect entity work-sets given as a conjunctive normal form (AND of OR-clauses) encoded in the
// path: `/` separates AND-clauses, `,` separates OR-operands, `:` separates `etype:id,id,...`.
// Returns the intersection ranked by citation count, capped at `n`, shaped exactly like the
// paginated works endpoint so the same UI renders it. See `rankless_trees::work_set::cnf_intersect`.
pub(crate) async fn intersect_get(
    Path(spec): Path<String>,
    Query(wq): Query<crate::responses::WorksQ>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let n = wq.n.unwrap_or(INTERSECT_DEFAULT_N).min(WORKS_PAGE_SIZE_MAX);
    let nstates = &states.0 .0;
    let gets = &states.0 .2.state.gets;

    let clause_strs: Vec<&str> = spec.split('/').filter(|s| !s.is_empty()).collect();
    if clause_strs.is_empty() || clause_strs.len() > INTERSECT_MAX_CLAUSES {
        return bad_text("bad clause count");
    }

    let mut clauses: Vec<Vec<&[WT]>> = Vec::with_capacity(clause_strs.len());
    let mut requested: Vec<ET<Authors>> = Vec::new();
    let mut total_operands = 0;
    for cs in clause_strs {
        let Some((etype, ids)) = cs.split_once(':') else {
            return bad_text("clause missing etype");
        };
        if !INTERSECTABLE.contains(&etype) {
            return bad_text("etype not intersectable");
        }
        let Some(ns) = nstates.get(etype) else {
            return bad_text("unknown etype");
        };
        let mut operands: Vec<&[WT]> = Vec::new();
        for raw_id in ids.split(',').filter(|s| !s.is_empty()) {
            total_operands += 1;
            if total_operands > INTERSECT_MAX_OPERANDS {
                return bad_text("too many operands");
            }
            // Unresolved ids drop out; a clause left with no operand makes the AND empty.
            if let Some(&dm_id) = ns.sem_to_dm.get(raw_id) {
                if let Some(slice) = gets.works_of_entity(dm_id as usize, etype.into()) {
                    operands.push(slice);
                }
                if etype == Authors::NAME {
                    requested.push(ET::<Authors>::from_usize(dm_id as usize));
                }
            }
        }
        clauses.push(operands);
    }

    match cnf_intersect(&clauses, INTERSECT_MAX_BASE) {
        Ok(mut wids) => {
            let total = wids.len();
            wids.sort_by_key(|&w| Reverse(gets.wccount(w.to_usize())));
            let top = wids.iter().take(n);
            let out = PaginatedPaperSetResp {
                resp: get_paper_set_resp(top, &requested, states.2.clone()),
                total_papers: total,
                slice_start: 0,
            };
            (cache_header(60), Json(out).into_response())
        }
        Err(_) => bad_text("couldn't intersect query, too broad"),
    }
}

pub(crate) async fn paper_profile(
    Path(author_sem_id): Path<String>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let Some((_, aid)) = resolve_dm(&states.0 .0, Authors::NAME, &author_sem_id) else {
        return get_empty();
    };
    let gets = &states.0 .2.state.gets;
    let hw_set: HashSet<WT> = hit_papers(root_cols(&states, Authors::NAME), aid)
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
        .chain(conn.wids.iter().filter(|wid| !hw_set.contains(*wid)));

    let papers = get_paper_set_resp(wids, &[ET::<Authors>::from_usize(aid)], states.2.clone());
    let out = PaperProfileResp {
        dag: conn.dag,
        papers,
    };
    (cache_header(60), Json(out).into_response())
}

// `requested_authors` are the authors the request is about: their rows are served on any work.
fn get_paper_set_resp<'a, I>(
    wids: I,
    requested_authors: &[ET<Authors>],
    trm: Arc<InstTrm>,
) -> PaperSetResp
where
    I: Iterator<Item = &'a WT>,
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
                requested_authors,
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
    requested_authors: &[ET<Authors>],
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
    let ships: Vec<Ship> = gets
        .wanyships(wid)
        .iter()
        .map(|anyship| {
            let (is_filtered, id) = reverse_prefixed_n(anyship.to_usize());
            if is_filtered {
                Ship {
                    pos: gets.fship_pos(&id).to_usize(),
                    author: ShipAuthor::Filtered(*gets.fshipa(&id)),
                    id,
                }
            } else {
                Ship {
                    pos: gets.dship_pos(&id).to_usize(),
                    author: ShipAuthor::Discarded(*gets.dshipa(&id)),
                    id,
                }
            }
        })
        .collect();
    let author_count = ships.len() as u32;
    let pinned = |aid: ET<Authors>| {
        requested_authors.contains(&aid) || gets.author_prizes(&aid.to_usize()).0 != 0
    };
    let authorships = served_ships(ships, pinned)
        .into_iter()
        .map(|ship| {
            let (author, insts) = match ship.author {
                ShipAuthor::Filtered(aid) => {
                    add_to_eatts(Authors::NAME, aid.to_usize());
                    authors_meta.entry(aid.to_usize()).or_insert_with(|| {
                        let prize_rec = gets.author_prizes(&aid.to_usize());
                        PaperAuthorMeta {
                            prize: prize_rec.0,
                            year: YearInterface::reverse(prize_rec.1),
                        }
                    });
                    (format!("F{aid}"), gets.fshipis(ship.id))
                }
                ShipAuthor::Discarded(aid) => {
                    let full_aid = format!("D{aid}");
                    if !discarded_author_name_map.contains_key(&full_aid) {
                        if let Some(name) = disc_name_handler.get_via_mut(&aid.to_usize()) {
                            discarded_author_name_map.insert(full_aid.clone(), name);
                        }
                    }
                    (full_aid, gets.dshipis(ship.id))
                }
            };
            let insts = insts
                .iter()
                .map(|iid| {
                    add_to_eatts(Institutions::NAME, iid.to_usize());
                    iid.to_usize()
                })
                .collect();
            PaperAuthorship { author, insts }
        })
        .collect();
    let source = gets.top_source(&wid).to_usize();
    add_to_eatts(Sources::NAME, source);
    let citations = gets.wccount(wid) as u32;
    let bar = *gets.wbar(&wid);
    let score = paper_score(citations, bar);

    PaperOut {
        wid,
        oa_id: gets.work_oa.get(wid).copied().unwrap_or(0),
        year: YearInterface::reverse(*gets.year(&wid)),
        name,
        hit_sem_id,
        doi,
        citations,
        yearly_cites,
        biblio,
        source,
        author_count,
        authorships,
        is_hit,
        bar: score.map(|_| decode_bar(bar)),
        score,
        created_topic,
    }
}

// A work's served authorship rows in position order. A row on discarded author 0, which holds
// every row OpenAlex left unresolved, is never served; past the first `team_limit` servable rows
// only the rows of `pinned` authors are.
fn served_ships(mut ships: Vec<Ship>, pinned: impl Fn(ET<Authors>) -> bool) -> Vec<Ship> {
    ships.sort_by_key(|s| s.pos);
    let mut servable = 0;
    ships.retain(|s| {
        let filtered = match s.author {
            ShipAuthor::Discarded(0) => return false,
            ShipAuthor::Discarded(_) => None,
            ShipAuthor::Filtered(aid) => Some(aid),
        };
        servable += 1;
        servable <= WORK_SCREEN.team_limit || filtered.is_some_and(&pinned)
    });
    ships
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ship(pos: usize, author: ShipAuthor) -> Ship {
        Ship {
            pos,
            author,
            id: pos,
        }
    }

    fn served(ships: Vec<Ship>, pinned: &[ET<Authors>]) -> Vec<(usize, ShipAuthor)> {
        served_ships(ships, |aid| pinned.contains(&aid))
            .into_iter()
            .map(|s| (s.pos, s.author))
            .collect()
    }

    #[test]
    fn team_serves_resolved_rows_in_position_order() {
        use ShipAuthor::*;
        let ships = vec![
            ship(2, Discarded(7)),
            ship(0, Filtered(3)),
            ship(1, Discarded(0)),
            ship(3, Discarded(0)),
            ship(4, Filtered(5)),
        ];
        assert_eq!(
            served(ships, &[]),
            vec![(0, Filtered(3)), (2, Discarded(7)), (4, Filtered(5))]
        );
    }

    #[test]
    fn large_work_serves_the_limit_plus_pinned_authors() {
        use ShipAuthor::*;
        let (requested, laureate) = (100_000, 200_000);
        let ships: Vec<Ship> = (0..3000)
            .rev()
            .map(|pos| {
                let author = match pos {
                    150 => Filtered(requested),
                    900 => Filtered(laureate),
                    p if p % 3 == 0 => Discarded(0),
                    p if p % 3 == 1 => Discarded(p as ET<AuthorshipDiscardedAuthor>),
                    p => Filtered(p as ET<Authors>),
                };
                ship(pos, author)
            })
            .collect();
        let out = served(ships, &[requested, laureate]);

        let limit = WORK_SCREEN.team_limit;
        let head: Vec<usize> = (0..3000).filter(|p| p % 3 != 0).take(limit).collect();
        let positions: Vec<usize> = out.iter().map(|(p, _)| *p).collect();
        assert_eq!(positions, [head, vec![150, 900]].concat());
        assert!(out.iter().all(|(_, a)| *a != Discarded(0)));
    }
}
