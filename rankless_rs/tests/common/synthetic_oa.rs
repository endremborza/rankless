//! Synthetic minimal OpenAlex snapshot in the layout `pyscripts/make_test_dataset.py` emits
//! (`data/<entity>/updated_date=…/part_000.gz`, gzipped JSON lines), sized from the compiled
//! `env_consts` thresholds so the bulk entities pass every filter screen. One part per entity
//! keeps `to-csv` single-threaded per entity, so CSV row order — and with it every dm id the
//! pipeline assigns — is a pure function of the scenario.
//!
//! The scenario is one pinned owner plus a keep/drop author pair and the works the ledger
//! kinds act on; `Scenario` names every id so a test (or the TS side, via `fixture-build`)
//! addresses them without parsing the snapshot.

use std::{
    fs::{create_dir_all, File},
    io::{self, BufWriter, Write},
    path::{Path, PathBuf},
};

use flate2::{write::GzEncoder, Compression};
use rankless_rs::env_consts::{
    FINAL_YEAR, MIN_AUTHOR_CITE_COUNT, MIN_AUTHOR_WORK_COUNT, MIN_PAPERS_FOR_INST,
    MIN_PAPERS_FOR_SOURCE,
};
use serde::Serialize;
use serde_json::{json, Value};

pub const OA: &str = "https://openalex.org/";
pub const ORCID: &str = "https://orcid.org/";
pub const DOI: &str = "https://doi.org/";
/// One more than the hyperauthorship ceiling `filter.rs` applies, so a work by all of them
/// only survives when forced.
pub const BULK_AUTHORS: usize = 24;
pub const PART_REL: &str = "updated_date=2026-01-01/part_000.gz";
/// Author slot of an authorship whose author record is missing (an empty `author` cell).
pub const NO_AUTHOR: u64 = 0;

pub const INST_A: u64 = 1001;
pub const INST_B: u64 = 1002;
pub const SOURCE: u64 = 2001;
pub const PUBLISHER: u64 = 3001;
pub const TOPIC: u64 = 10001;
pub const SUBFIELD: u64 = 1101;
pub const FIELD: u64 = 11;
pub const DOMAIN: u64 = 1;

#[derive(Serialize)]
pub struct Person {
    pub oa_id: u64,
    pub orcid: Option<&'static str>,
    pub name: &'static str,
    pub works_count: u32,
    pub cited_by_count: u32,
}

#[derive(Serialize)]
pub struct WorkSpec {
    pub oa_id: u64,
    pub doi: Option<String>,
    pub kind: &'static str,
    pub title: String,
    /// (author oa_id, institution oa_id) in authorship order
    pub authors: Vec<(u64, u64)>,
    pub refs: Vec<u64>,
}

#[derive(Serialize)]
pub struct Scenario {
    pub year: u16,
    /// Signs in (owner pin), sits below the author thresholds, disowns two works.
    pub owner: Person,
    /// Keep side of the author merge; claims by DOI.
    pub keep: Person,
    /// Drop side of the author merge; no ORCID.
    pub drop: Person,
    /// Has an ORCID but no authorship anywhere; claims a work that is not theirs.
    pub outsider: Person,
    pub bulk_authors: Vec<Person>,
    pub works: Vec<WorkSpec>,
    /// Owner's only-author article: disowning it leaves the work authorless.
    pub solo: u64,
    /// Owner + a bulk author: disowning it only removes the owner's edge.
    pub shared: u64,
    /// Owner's `dataset`-typed work: fails the type screen unless forced.
    pub dataset: u64,
    /// Owner's article no work references: fails the citation screen unless forced.
    pub uncited: u64,
    /// Owner + every bulk author: above `MAX_AUTHORS` unless forced.
    pub hyper: u64,
    pub keep_work: u64,
    pub drop_work: u64,
    /// Preprint by `keep`; its DOI claim applies directly.
    pub claim_auto: u64,
    /// Preprint by `drop`; `keep`'s claim applies through the author merge.
    pub claim_merged: u64,
    /// Article with a DOI that neither `keep` nor `outsider` is on; its last authorship
    /// carries no author record (`NO_AUTHOR`), as OpenAlex emits for unresolved names.
    pub not_mine: u64,
    pub ghost_work: u64,
    pub ghost_author: u64,
    pub ghost_doi: &'static str,
    pub unknown_orcid: &'static str,
}

impl Person {
    const fn new(
        oa_id: u64,
        orcid: Option<&'static str>,
        name: &'static str,
        works_count: u32,
        cited_by_count: u32,
    ) -> Self {
        Self {
            oa_id,
            orcid,
            name,
            works_count,
            cited_by_count,
        }
    }
}

impl Scenario {
    pub fn new() -> Self {
        let year = FINAL_YEAR - 1;
        let above_works = MIN_AUTHOR_WORK_COUNT as u32 + 5;
        let above_cites = MIN_AUTHOR_CITE_COUNT as u32 + 5;
        let owner = Person::new(5100001, Some("0000-0001-0000-0001"), "Olga Owner", 3, 5);
        let keep = Person::new(
            5100002,
            Some("0000-0001-0000-0002"),
            "Kim Keep",
            above_works,
            above_cites,
        );
        let drop = Person::new(5100003, None, "Dan Drop", above_works, above_cites);
        let outsider = Person::new(
            5100004,
            Some("0000-0001-0000-0004"),
            "Otto Outsider",
            above_works,
            above_cites,
        );
        let bulk_authors: Vec<Person> = (0..BULK_AUTHORS)
            .map(|k| {
                Person::new(
                    5000000 + k as u64,
                    None,
                    BULK_NAMES[k],
                    above_works,
                    above_cites,
                )
            })
            .collect();
        let bulk = |k: usize| bulk_authors[k % BULK_AUTHORS].oa_id;

        let n_bulk = MIN_PAPERS_FOR_INST.max(MIN_PAPERS_FOR_SOURCE) as usize + 8;
        let bulk_work = |b: usize| 7000000 + b as u64;
        let mut works: Vec<WorkSpec> = (0..n_bulk)
            .map(|b| {
                let mut authors = vec![(bulk(b), INST_A), (bulk(b + 1), INST_B)];
                if b % 5 == 0 {
                    authors.push((keep.oa_id, INST_A));
                }
                if b % 7 == 0 {
                    authors.push((drop.oa_id, INST_B));
                }
                WorkSpec {
                    oa_id: bulk_work(b),
                    doi: Some(format!("10.5555/bulk.{b}")),
                    kind: "article",
                    title: format!("Bulk study number {b}"),
                    authors,
                    refs: vec![bulk_work((b + n_bulk - 1) % n_bulk)],
                }
            })
            .collect();

        let [solo, shared, dataset, uncited, hyper, keep_work, drop_work, claim_auto, claim_merged, not_mine] =
            core::array::from_fn(|i| 7100001 + i as u64);
        let mut hyper_authors: Vec<(u64, u64)> =
            bulk_authors.iter().map(|p| (p.oa_id, INST_A)).collect();
        hyper_authors.push((owner.oa_id, INST_A));
        works.extend([
            spec(
                solo,
                None,
                "article",
                "Solo owner article",
                vec![(owner.oa_id, INST_A)],
                vec![shared],
            ),
            spec(
                shared,
                None,
                "article",
                "Shared owner article",
                vec![(owner.oa_id, INST_A), (bulk(0), INST_A)],
                vec![
                    solo,
                    dataset,
                    hyper,
                    keep_work,
                    drop_work,
                    claim_auto,
                    claim_merged,
                    not_mine,
                ],
            ),
            spec(
                dataset,
                None,
                "dataset",
                "Owner dataset",
                vec![(owner.oa_id, INST_A), (bulk(1), INST_B)],
                vec![],
            ),
            spec(
                uncited,
                None,
                "article",
                "Uncited owner article",
                vec![(owner.oa_id, INST_A), (bulk(2), INST_A)],
                vec![shared],
            ),
            spec(
                hyper,
                None,
                "article",
                "Hyperauthored consortium paper",
                hyper_authors,
                vec![],
            ),
            spec(
                keep_work,
                None,
                "article",
                "Kept twin",
                vec![(bulk(3), INST_A)],
                vec![drop_work],
            ),
            spec(
                drop_work,
                None,
                "article",
                "Dropped twin",
                vec![(bulk(3), INST_A), (keep.oa_id, INST_A)],
                vec![keep_work],
            ),
            spec(
                claim_auto,
                Some("10.5555/claim.auto"),
                "preprint",
                "Claimed preprint",
                vec![(keep.oa_id, INST_A), (bulk(0), INST_A)],
                vec![],
            ),
            spec(
                claim_merged,
                Some("10.5555/claim.merged"),
                "preprint",
                "Preprint under the dropped name",
                vec![(drop.oa_id, INST_B), (bulk(1), INST_B)],
                vec![],
            ),
            spec(
                not_mine,
                Some("10.5555/not.mine"),
                "article",
                "Somebody else's article",
                vec![(bulk(2), INST_A), (bulk(3), INST_A), (NO_AUTHOR, INST_B)],
                vec![],
            ),
        ]);

        Self {
            year,
            owner,
            keep,
            drop,
            outsider,
            bulk_authors,
            works,
            solo,
            shared,
            dataset,
            uncited,
            hyper,
            keep_work,
            drop_work,
            claim_auto,
            claim_merged,
            not_mine,
            ghost_work: 7999999,
            ghost_author: 5999999,
            ghost_doi: "10.5555/ghost",
            unknown_orcid: "0000-0009-9999-9999",
        }
    }

    pub fn work(&self, oa_id: u64) -> &WorkSpec {
        self.works.iter().find(|w| w.oa_id == oa_id).unwrap()
    }

    pub fn persons(&self) -> impl Iterator<Item = &Person> {
        [&self.owner, &self.keep, &self.drop, &self.outsider]
            .into_iter()
            .chain(self.bulk_authors.iter())
    }

    /// The `to-csv` input directory.
    pub fn data_dir(snapshot_dir: &Path) -> PathBuf {
        snapshot_dir.join("data")
    }

    pub fn write_snapshot(&self, snapshot_dir: &Path) -> io::Result<()> {
        let data = Self::data_dir(snapshot_dir);
        let cited_by = |wid: u64| self.works.iter().filter(|w| w.refs.contains(&wid)).count();
        write_entity(
            &data,
            "works",
            self.works
                .iter()
                .map(|w| self.work_json(w, cited_by(w.oa_id))),
        )?;
        write_entity(&data, "authors", self.persons().map(author_json))?;
        write_entity(
            &data,
            "institutions",
            [
                inst_json(INST_A, "Alpha University", "HU", "Budapest", 47.5, 19.05),
                inst_json(INST_B, "Beta Institute", "US", "Boston", 42.36, -71.06),
            ]
            .into_iter(),
        )?;
        write_entity(&data, "sources", [source_json()].into_iter())?;
        write_entity(&data, "publishers", [publisher_json()].into_iter())?;
        write_entity(&data, "topics", [topic_json()].into_iter())?;
        write_entity(&data, "subfields", [subfield_json()].into_iter())?;
        write_entity(&data, "fields", [field_json()].into_iter())?;
        write_entity(&data, "domains", [domain_json()].into_iter())
    }

    fn work_json(&self, w: &WorkSpec, cited_by_count: usize) -> Value {
        let id = oa(&format!("W{}", w.oa_id));
        let doi = w.doi.as_ref().map(|d| format!("{DOI}{d}"));
        let last = w.authors.len().saturating_sub(1);
        let authorships: Vec<Value> = w
            .authors
            .iter()
            .enumerate()
            .map(|(i, (aid, iid))| {
                let author = match self.persons().find(|p| p.oa_id == *aid) {
                    Some(p) => json!({"id": oa(&format!("A{aid}")), "display_name": p.name, "orcid": p.orcid.map(|o| format!("{ORCID}{o}"))}),
                    None => json!({"id": null, "display_name": "Unresolved Name", "orcid": null}),
                };
                json!({
                    "author": author,
                    "institutions": [{"id": oa(&format!("I{iid}")), "display_name": inst_name(*iid), "country_code": inst_country(*iid)}],
                    "author_position": if i == 0 { "first" } else if i == last { "last" } else { "middle" },
                    "raw_affiliation_string": inst_name(*iid),
                })
            })
            .collect();
        let topic = json!({"id": oa(&format!("T{TOPIC}")), "display_name": "Synthetic Topic", "score": 0.9,
            "subfield": {"id": oa(&format!("subfields/{SUBFIELD}")), "display_name": "Synthetic Subfield"},
            "field": {"id": oa(&format!("fields/{FIELD}")), "display_name": "Synthetic Field"},
            "domain": {"id": oa(&format!("domains/{DOMAIN}")), "display_name": "Synthetic Domain"}});
        let location = json!({"source": {"id": oa(&format!("S{SOURCE}")), "display_name": "Journal of Synthesis"},
            "is_oa": false, "landing_page_url": doi, "version": null, "license": null});
        json!({
            "id": id,
            "doi": doi,
            "title": w.title,
            "display_name": w.title,
            "ids": {"openalex": id, "doi": doi},
            "publication_year": self.year,
            "publication_date": format!("{}-03-01", self.year),
            "language": "en",
            "type": w.kind,
            "authorships": authorships,
            "primary_topic": topic,
            "topics": [topic],
            "primary_location": location,
            "locations": [location],
            "biblio": {"volume": "1", "issue": "1", "first_page": "1", "last_page": "10"},
            "open_access": {"is_oa": false, "oa_status": "closed", "oa_url": null},
            "referenced_works": w.refs.iter().map(|r| oa(&format!("W{r}"))).collect::<Vec<_>>(),
            "cited_by_count": cited_by_count,
            "counts_by_year": [],
            "is_retracted": false,
            "is_paratext": false,
            "updated_date": "2026-01-01",
        })
    }
}

impl Default for Scenario {
    fn default() -> Self {
        Self::new()
    }
}

const BULK_NAMES: [&str; BULK_AUTHORS] = [
    "Ada Bulk",
    "Ben Bulk",
    "Cy Bulk",
    "Di Bulk",
    "Ed Bulk",
    "Fay Bulk",
    "Gus Bulk",
    "Hal Bulk",
    "Ida Bulk",
    "Jo Bulk",
    "Kai Bulk",
    "Lu Bulk",
    "Mo Bulk",
    "Ned Bulk",
    "Oz Bulk",
    "Pat Bulk",
    "Quinn Bulk",
    "Ro Bulk",
    "Sam Bulk",
    "Tia Bulk",
    "Uma Bulk",
    "Vic Bulk",
    "Wes Bulk",
    "Xi Bulk",
];

fn spec(
    oa_id: u64,
    doi: Option<&str>,
    kind: &'static str,
    title: &str,
    authors: Vec<(u64, u64)>,
    refs: Vec<u64>,
) -> WorkSpec {
    WorkSpec {
        oa_id,
        doi: doi.map(str::to_string),
        kind,
        title: title.to_string(),
        authors,
        refs,
    }
}

fn oa(tail: &str) -> String {
    format!("{OA}{tail}")
}

fn inst_name(iid: u64) -> &'static str {
    match iid {
        INST_A => "Alpha University",
        _ => "Beta Institute",
    }
}

fn inst_country(iid: u64) -> &'static str {
    match iid {
        INST_A => "HU",
        _ => "US",
    }
}

fn author_json(p: &Person) -> Value {
    let id = oa(&format!("A{}", p.oa_id));
    let orcid = p.orcid.map(|o| format!("{ORCID}{o}"));
    json!({
        "id": id,
        "display_name": p.name,
        "display_name_alternatives": [],
        "orcid": orcid,
        "works_count": p.works_count,
        "cited_by_count": p.cited_by_count,
        "summary_stats": {"2yr_mean_citedness": 1.0, "h_index": 3, "i10_index": 2},
        "ids": {"openalex": id, "orcid": orcid},
        "counts_by_year": [],
        "updated_date": "2026-01-01",
    })
}

fn inst_json(iid: u64, name: &str, cc: &str, city: &str, lat: f64, lon: f64) -> Value {
    let id = oa(&format!("I{iid}"));
    json!({
        "id": id,
        "ror": format!("https://ror.org/0{iid}"),
        "display_name": name,
        "country_code": cc,
        "type": "education",
        "homepage_url": format!("https://{iid}.example.org"),
        "image_url": null,
        "image_thumbnail_url": null,
        "display_name_acronyms": [],
        "display_name_alternatives": [],
        "works_count": 1000,
        "cited_by_count": 10000,
        "ids": {"openalex": id},
        "geo": {"city": city, "geonames_city_id": null, "region": null, "country_code": cc, "country": cc, "latitude": lat, "longitude": lon},
        "associated_institutions": [],
        "counts_by_year": [],
        "updated_date": "2026-01-01",
    })
}

fn source_json() -> Value {
    let id = oa(&format!("S{SOURCE}"));
    json!({
        "id": id,
        "issn_l": null,
        "issn": [],
        "display_name": "Journal of Synthesis",
        "host_organization": oa(&format!("P{PUBLISHER}")),
        "works_count": 1000,
        "cited_by_count": 10000,
        "is_oa": false,
        "is_in_doaj": false,
        "homepage_url": null,
        "alternate_titles": [],
        "type": "journal",
        "ids": {"openalex": id},
        "counts_by_year": [],
        "updated_date": "2026-01-01",
    })
}

fn publisher_json() -> Value {
    let id = oa(&format!("P{PUBLISHER}"));
    json!({
        "id": id,
        "display_name": "Synthetic Press",
        "alternate_titles": [],
        "country_codes": ["HU"],
        "hierarchy_level": 0,
        "parent_publisher": null,
        "works_count": 1000,
        "cited_by_count": 10000,
        "ids": {"openalex": id},
        "counts_by_year": [],
        "updated_date": "2026-01-01",
    })
}

fn topic_json() -> Value {
    let id = oa(&format!("T{TOPIC}"));
    json!({
        "id": id,
        "display_name": "Synthetic Topic",
        "subfield": {"id": oa(&format!("subfields/{SUBFIELD}")), "display_name": "Synthetic Subfield"},
        "field": {"id": oa(&format!("fields/{FIELD}")), "display_name": "Synthetic Field"},
        "domain": {"id": oa(&format!("domains/{DOMAIN}")), "display_name": "Synthetic Domain"},
        "ids": {"openalex": id},
        "works_count": 1000,
        "cited_by_count": 10000,
        "updated_date": "2026-01-01",
    })
}

fn subfield_json() -> Value {
    let id = oa(&format!("subfields/{SUBFIELD}"));
    json!({
        "id": id,
        "display_name": "Synthetic Subfield",
        "field": {"id": oa(&format!("fields/{FIELD}")), "display_name": "Synthetic Field"},
        "domain": {"id": oa(&format!("domains/{DOMAIN}")), "display_name": "Synthetic Domain"},
        "ids": {"openalex": id},
        "works_count": 1000,
        "cited_by_count": 10000,
        "updated_date": "2026-01-01",
    })
}

fn field_json() -> Value {
    let id = oa(&format!("fields/{FIELD}"));
    json!({
        "id": id,
        "display_name": "Synthetic Field",
        "domain": {"id": oa(&format!("domains/{DOMAIN}")), "display_name": "Synthetic Domain"},
        "ids": {"openalex": id},
        "works_count": 1000,
        "cited_by_count": 10000,
        "updated_date": "2026-01-01",
    })
}

fn domain_json() -> Value {
    let id = oa(&format!("domains/{DOMAIN}"));
    json!({
        "id": id,
        "display_name": "Synthetic Domain",
        "ids": {"openalex": id},
        "works_count": 1000,
        "cited_by_count": 10000,
        "updated_date": "2026-01-01",
    })
}

fn write_entity(data: &Path, entity: &str, lines: impl Iterator<Item = Value>) -> io::Result<()> {
    let path = data.join(entity).join(PART_REL);
    create_dir_all(path.parent().unwrap())?;
    let mut gz = BufWriter::new(GzEncoder::new(File::create(path)?, Compression::fast()));
    for line in lines {
        serde_json::to_writer(&mut gz, &line)?;
        gz.write_all(b"\n")?;
    }
    gz.flush()
}
