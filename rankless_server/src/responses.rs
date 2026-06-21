use std::sync::Arc;

use dmove::{Entity, UnsignedNumber, ET};
use hashbrown::HashMap;
use serde::{Deserialize, Serialize};

use rankless_rs::{
    gen::a2_init_atts::WorkBiblios,
    steps::{a1_entity_mapping::RawYear, derive_links2::EraRec},
};
use rankless_trees::{
    interfacing::{RootInterfaceable, RootInterfaces},
    io::EntityAttsForLinks,
    path_finder::RefDAG,
};

#[derive(Serialize, Clone)]
pub(crate) struct SearchResult {
    pub name: Arc<str>,
    #[serde(rename = "semanticId")]
    pub semantic_id: Arc<str>,
    #[serde(rename = "oaId")]
    pub oa_id: u64,
    #[serde(rename = "dmId")]
    pub dm_id: usize,
    #[serde(rename = "distinctText", skip_serializing_if = "Option::is_none")]
    pub distinct_text: Option<String>,
    pub papers: u32,
    pub citations: u32,
    // Total (unfiltered) OpenAlex citation count; carried only for authors, omitted otherwise.
    #[serde(rename = "rawCites", skip_serializing_if = "Option::is_none")]
    pub raw_cites: Option<u32>,
}

#[derive(Serialize)]
pub(crate) struct UnionSearchResult {
    #[serde(flatten)]
    pub sr: SearchResult,
    #[serde(rename = "rootType")]
    pub root_type: &'static str,
}

#[derive(Serialize, Clone)]
pub(crate) struct SerializableExt {
    #[serde(rename = "startYear")]
    pub start_year: RawYear,
    #[serde(rename = "yearlyPapers")]
    pub yearly_papers: EraRec,
    #[serde(rename = "yearlyCites")]
    pub yearly_cites: EraRec,
    pub relations: RelationGroups,
    #[serde(rename = "authorNetwork")]
    pub author_network: Box<[u8]>,
}

// Hero relations grouped by relation type, keyed by the names the frontend consumes directly (no
// numeric rel-type contract, no client-side regrouping). Built per request from the mmapped top-N
// tables.
#[derive(Serialize, Clone, Default)]
pub(crate) struct RelationGroups {
    #[serde(rename = "paper-fields")]
    pub paper_fields: Vec<PostAttRelatedEntity>,
    #[serde(rename = "citing-fields")]
    pub citing_fields: Vec<PostAttRelatedEntity>,
    #[serde(rename = "paper-topics")]
    pub paper_topics: Vec<PostAttRelatedEntity>,
    #[serde(rename = "citing-topics")]
    pub citing_topics: Vec<PostAttRelatedEntity>,
    #[serde(rename = "collab-nation")]
    pub collab_nation: Vec<PostAttRelatedEntity>,
    #[serde(rename = "paper-journals")]
    pub paper_journals: Vec<PostAttRelatedEntity>,
    #[serde(rename = "paper-authors")]
    pub paper_authors: Vec<PostAttRelatedEntity>,
}

#[derive(Serialize, Clone)]
pub(crate) struct PostAttRelatedEntity {
    pub name: String,
    #[serde(rename = "semanticId")]
    pub semantic_id: String,
    pub etype: String,
    pub score: u32,
    // Parent subfield label for topic relations, so the hero can nest topics under their field.
    #[serde(rename = "parentName", skip_serializing_if = "Option::is_none")]
    pub parent_name: Option<String>,
    #[serde(rename = "parentSemanticId", skip_serializing_if = "Option::is_none")]
    pub parent_semantic_id: Option<String>,
}

#[derive(Serialize)]
pub(crate) struct ViewResult {
    #[serde(flatten)]
    pub sr: SearchResult,
    #[serde(flatten)]
    pub ext: SerializableExt,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub meta: Option<HashMap<&'static str, String>>,
    pub similars: Vec<SearchResult>,
}

#[derive(Serialize)]
pub(crate) struct TopResult {
    pub name: String,
    pub entities: Vec<SearchResult>,
}

#[derive(Serialize)]
pub(crate) struct EntityDescription {
    pub name: String,
    pub count: usize,
}

#[derive(Serialize)]
pub(crate) struct CountsResponse {
    pub entities: Vec<EntityDescription>,
    pub total_citations: u64,
    pub total_works: usize,
}

#[derive(Serialize)]
pub(crate) struct PeerSubfieldInfo {
    pub name: Arc<str>,
    #[serde(rename = "semanticId")]
    pub semantic_id: Arc<str>,
    #[serde(rename = "dmId")]
    pub dm_id: usize,
}

#[derive(Serialize)]
pub(crate) struct PeerEntry {
    //TODO - this should just be another view
    pub name: Arc<str>,
    #[serde(rename = "semanticId")]
    pub semantic_id: Arc<str>,
    pub papers: u32,
    pub citations: u32,
    #[serde(rename = "subfieldCitations")]
    pub subfield_citations: Vec<u32>,
    #[serde(rename = "yearlyPapers")]
    pub yearly_papers: EraRec,
    #[serde(rename = "yearlyCites")]
    pub yearly_cites: EraRec,
    #[serde(rename = "startYear")]
    pub start_year: RawYear,
    #[serde(rename = "hIndex", skip_serializing_if = "Option::is_none")]
    pub h_index: Option<u32>,
    #[serde(rename = "yearCentroid", skip_serializing_if = "Option::is_none")]
    pub year_centroid: Option<f32>,
    pub country: Option<Arc<str>>,
}

#[derive(Serialize)]
pub(crate) struct EntityPeersResp {
    #[serde(rename = "topSubfields")]
    pub top_subfields: Vec<PeerSubfieldInfo>,
    pub peers: Vec<PeerEntry>,
    pub hero: PeerEntry,
}

// Per-cohort-entity-type rank-breakpoint table the client caches once per root type and uses to tag
// any citation count with its subfield standing (the standing is computed on the frontend).
#[derive(Serialize)]
pub(crate) struct LadderResp {
    #[serde(rename = "pctBands")]
    pub pct_bands: &'static [f64],
    // One row per subfield dm_id; each cell is the citation threshold for that percentile band, or
    // null when the cohort is too small for it.
    pub ladder: Vec<Vec<Option<u32>>>,
}

#[derive(Serialize)]
pub(crate) struct StatsSubfield {
    pub name: Arc<str>,
    #[serde(rename = "semanticId")]
    pub semantic_id: Arc<str>,
    #[serde(rename = "dmId")]
    pub dm_id: usize,
    pub citations: u32,
}

// Flat, agent-friendly aggregate for one entity. `papers`/`citations` are lifetime (indexed)
// totals; per-year resolution exists only for the recent era (`eraFrom`..`eraTo`), so the windowed
// figures are clamped to that span. `topSubfields`/`subfield` are the citing-subfield impact
// profile and are only populated for root types that carry one (authors/institutions/countries/
// sources).
#[derive(Serialize)]
pub(crate) struct StatsResp {
    pub name: Arc<str>,
    #[serde(rename = "semanticId")]
    pub semantic_id: Arc<str>,
    #[serde(rename = "dmId")]
    pub dm_id: usize,
    pub papers: u32,
    pub citations: u32,
    #[serde(rename = "eraFrom")]
    pub era_from: RawYear,
    #[serde(rename = "eraTo")]
    pub era_to: RawYear,
    #[serde(rename = "windowFrom")]
    pub window_from: RawYear,
    #[serde(rename = "windowTo")]
    pub window_to: RawYear,
    #[serde(rename = "windowPapers")]
    pub window_papers: u32,
    #[serde(rename = "windowCitations")]
    pub window_citations: u32,
    #[serde(rename = "yearlyPapers")]
    pub yearly_papers: Vec<u32>,
    #[serde(rename = "yearlyCites")]
    pub yearly_cites: Vec<u32>,
    #[serde(rename = "topSubfields")]
    pub top_subfields: Vec<StatsSubfield>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub subfield: Option<StatsSubfield>,
}

#[derive(Serialize)]
pub(crate) struct ResolveWorkResp {
    #[serde(rename = "oaId")]
    pub oa_id: u64,
    pub wid: usize,
    pub doi: String,
    pub year: u16,
    pub name: String,
}

#[derive(Serialize)]
pub(crate) struct ResolveAuthorResp {
    #[serde(rename = "oaId")]
    pub oa_id: u64,
    #[serde(rename = "dmId")]
    pub dm_id: usize,
    #[serde(rename = "semanticId")]
    pub semantic_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub orcid: Option<String>,
    pub name: String,
}

#[derive(Serialize, Clone)]
pub(crate) struct PaperAuthorship {
    pub author: String, //prefixed with filtered/discarded
    pub insts: Vec<usize>,
}

#[derive(Serialize)]
pub(crate) struct PaperOut {
    pub wid: usize,
    #[serde(rename = "oaId")]
    pub oa_id: u64,
    pub year: u16,
    pub name: String,
    pub doi: String,
    pub citations: u32,
    pub source: usize,
    pub authorships: Vec<PaperAuthorship>,
    #[serde(rename = "yearlyCites", skip_serializing_if = "Option::is_none")]
    pub yearly_cites: Option<Box<[u32]>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub biblio: Option<ET<WorkBiblios>>,
    #[serde(rename = "isHit")]
    pub is_hit: bool,
    #[serde(rename = "hitBm", skip_serializing_if = "Option::is_none")]
    pub hit_bm: Option<u32>,
    #[serde(rename = "hitSemId", skip_serializing_if = "Option::is_none")]
    pub hit_sem_id: Option<String>,
    #[serde(rename = "createdTopic", skip_serializing_if = "Option::is_none")]
    pub created_topic: Option<String>,
}

#[derive(Serialize)]
pub(crate) struct PaperAuthorMeta {
    pub prize: u8,
    pub year: u16,
}

#[derive(Serialize)]
pub(crate) struct PaperSetResp {
    pub papers: Vec<PaperOut>,
    #[serde(rename = "entityAtts")]
    pub entity_atts: EntityAttsForLinks,
    #[serde(rename = "discAuthorNames")]
    pub disc_author_names: HashMap<String, String>,
    #[serde(rename = "authorsMeta")]
    pub authors_meta: HashMap<usize, PaperAuthorMeta>, //only filtered authors
}

#[derive(Serialize)]
pub(crate) struct PaginatedPaperSetResp {
    pub resp: PaperSetResp,
    #[serde(rename = "totalPapers")]
    pub total_papers: usize,
    #[serde(rename = "sliceStart")]
    pub slice_start: usize,
}

#[derive(Serialize)]
pub(crate) struct PaperProfileResp {
    pub dag: RefDAG,
    pub papers: PaperSetResp,
}

#[derive(Deserialize)]
pub(crate) struct BasicQ {
    pub q: Option<String>,
}

#[derive(Deserialize)]
pub(crate) struct WorksQ {
    pub n: Option<usize>,
}

#[derive(Deserialize)]
pub(crate) struct StatsQ {
    pub year_from: Option<u16>,
    pub year_to: Option<u16>,
    pub subfield: Option<String>,
}

#[derive(Deserialize)]
pub(crate) struct ResolveWorkQ {
    pub wid: Option<usize>,
    pub oa_id: Option<u64>,
    pub doi: Option<String>,
}

#[derive(Deserialize)]
pub(crate) struct ResolveAuthorQ {
    pub semantic_id: Option<String>,
    pub orcid: Option<String>,
    pub oa_id: Option<u64>,
    pub dm_id: Option<usize>,
}

impl SearchResult {
    pub fn new<E>(
        i: usize,
        name: Arc<str>,
        semantic_id: Arc<str>,
        distinct_text: Option<String>,
        raw_cites: Option<u32>,
        entif: &RootInterfaces<E>,
    ) -> Self
    where
        E: RootInterfaceable,
    {
        let papers = if entif.wcounts.len() > i {
            entif.wcounts[i].to_usize()
        } else {
            1
        } as u32;
        Self {
            name,
            semantic_id,
            distinct_text,
            papers,
            citations: entif.ccounts[i].to_usize() as u32,
            raw_cites,
            oa_id: entif.oa_id[i],
            dm_id: i,
        }
    }
}

impl EntityDescription {
    pub fn new<E: Entity>(count: usize) -> Self {
        Self {
            name: <E as Entity>::NAME.to_string(),
            count,
        }
    }
}
