//! `derive-ledger`: the identity records OpenAlex's author split implies, written in the ledger's
//! own format as one more source (`user-ledger/derived.jsonl`). The author records sharing an
//! ORCID are one person's unless their names say otherwise: each ORCID's records are clustered by
//! name; the cluster the ORCID's registered name matches (else the one with the most works) owns
//! it; the owner's oldest record keeps; every other record of the ORCID is merged into the keep or
//! stripped of the ORCID. A record over the author screen's work bound never owns or keeps.

use std::{
    collections::BTreeMap,
    env,
    fs::File,
    hash::{DefaultHasher, Hash, Hasher},
    io::{self, BufRead, BufReader, BufWriter, Write},
    path::{Path, PathBuf},
};

use dmove::BigId;
use hashbrown::{HashMap, HashSet};
use serde::Serialize;

use crate::{
    common::{ParsedId, Stowage, MAIN_NAME},
    csv_iter::par_reduce,
    csv_writers::authors,
    metrics::WORK_SCREEN,
    oa_structs::post::Author,
    user_ledger::{normalize_orcid, write_json, DERIVED_JSONL, DERIVED_MANIFEST},
};

pub const EXTERNAL_DATA_ROOT: &str = "EXTERNAL_DATA_ROOT";
/// The root when the variable is unset: a dev box, relative to the repo root the pipeline runs from.
pub const DEFAULT_EXTERNAL_DATA_ROOT: &str = "data/external";
pub const NAMES_TABLE: &str = "orcid/names.tsv.zst";
pub const SOURCE: &str = "derived";

/// Bits of shared name information two records need to be one person: two common tokens
/// (about 7 and 9 bits) fall short of it once two initials disagree, one common token plus a
/// matching initial clears it.
const MATCH_BITS: f64 = 11.0;
/// A full token only one side has, and an initial only one side has.
const EXTRA_TOKEN_BITS: f64 = 8.0;
const EXTRA_INITIAL_BITS: f64 = 4.0;
/// An initial matched to a full token's first letter, or to the same initial.
const INITIAL_MATCH_BITS: f64 = 5.0;

type OrcidCode = u64;

#[derive(Default, Serialize)]
pub struct DerivedManifest {
    pub author_rows: u64,
    pub orcids: usize,
    pub records: usize,
    pub registered_names: bool,
    pub owner_by: BTreeMap<Reason, usize>,
    pub merges: BTreeMap<Reason, usize>,
    pub strips: BTreeMap<Reason, usize>,
}

/// A name as compared: full tokens folded to lowercase ASCII where a fold exists, in the order
/// written, with their sorted hashes for the identity test; initials apart, sorted. A raw token
/// of up to three capitals ("HG", "SP") is that many initials.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Name {
    tokens: Vec<String>,
    sorted: Vec<u64>,
    initials: Vec<char>,
}

/// Token frequencies over every author name, for the information content of a shared token.
#[derive(Default)]
pub struct Freq {
    counts: HashMap<u64, u32>,
    total: u64,
}

struct Rec {
    orcid: String,
    id: BigId,
    name: Name,
    works: u32,
}

#[derive(Default)]
struct Census {
    rows: u64,
    orcids: HashMap<OrcidCode, u32>,
    freq: Freq,
}

struct Record {
    orcid: String,
    decision: Decision,
}

/// Which tokens of the two names are still unmatched.
struct Open {
    a: Vec<bool>,
    b: Vec<bool>,
}

/// What two names share and what each has left unmatched.
struct Residue {
    shared: f64,
    a_tokens: usize,
    a_initials: usize,
    b_tokens: usize,
    b_initials: usize,
}

/// Why a record is merged (how its ORCID's owner cluster was chosen) or stripped.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Reason {
    RegisteredName,
    MostWorks,
    /// A cluster outside the owner's that no registered name contradicts.
    CompatibleName,
    NameMismatch,
    OverWorkBound,
}

#[derive(Debug, PartialEq, Eq)]
enum Decision {
    Merge {
        drop: BigId,
        keep: BigId,
        reason: Reason,
    },
    Strip {
        id: BigId,
        reason: Reason,
    },
}

impl Name {
    pub fn parse(raw: &str) -> Self {
        let (mut tokens, mut initials): (Vec<String>, Vec<char>) = (Vec::new(), Vec::new());
        for raw_tok in raw
            .split(|c: char| !c.is_alphanumeric())
            .filter(|t| !t.is_empty())
        {
            if raw_tok.chars().all(|c| c.is_ascii_digit()) {
                continue;
            }
            let capitals =
                raw_tok.chars().count() <= 3 && raw_tok.chars().all(|c| c.is_ascii_uppercase());
            let tok = fold(raw_tok);
            if capitals || tok.chars().count() == 1 {
                initials.extend(tok.chars());
            } else {
                tokens.push(tok);
            }
        }
        let mut sorted: Vec<u64> = tokens.iter().map(|t| token_hash(t)).collect();
        sorted.sort_unstable();
        initials.sort_unstable();
        Self {
            tokens,
            sorted,
            initials,
        }
    }

    fn is_empty(&self) -> bool {
        self.tokens.is_empty() && self.initials.is_empty()
    }

    /// The same tokens and initials in any order.
    fn alike(&self, other: &Self) -> bool {
        self.sorted == other.sorted && self.initials == other.initials
    }
}

impl Freq {
    fn add(&mut self, name: &str) {
        for tok in Name::parse(name).tokens {
            *self.counts.entry(token_hash(&tok)).or_default() += 1;
            self.total += 1;
        }
    }

    fn merge(&mut self, other: Freq) {
        for (k, v) in other.counts {
            *self.counts.entry(k).or_default() += v;
        }
        self.total += other.total;
    }

    /// `log2(total / count)`; a token never counted is as rare as one seen once.
    pub fn ic(&self, token: u64) -> f64 {
        let count = self.counts.get(&token).copied().unwrap_or(1).max(1);
        (self.total.max(1) as f64 / count as f64).log2()
    }
}

impl Open {
    fn find_b(&self, pred: impl Fn(usize) -> bool) -> Option<usize> {
        (0..self.b.len()).find(|&j| self.b[j] && pred(j))
    }

    fn take(&mut self, i: usize, j: usize) {
        self.a[i] = false;
        self.b[j] = false;
    }

    fn swap(&mut self) {
        std::mem::swap(&mut self.a, &mut self.b);
    }

    fn firsts_a(&self, a: &Name) -> Vec<char> {
        firsts(a, &self.a)
    }

    fn firsts_b(&self, b: &Name) -> Vec<char> {
        firsts(b, &self.b)
    }
}

/// Shared minus unshared name information in bits; identical names are infinitely alike. A
/// token matches the same token, one written as two adjacent tokens ("xianglei" ~ "xiang
/// lei") or one it begins ("ben" ~ "benjamin"); an initial matches the same initial or the
/// first letter of an otherwise unmatched token.
pub fn affinity(a: &Name, b: &Name, freq: &Freq) -> f64 {
    if a.alike(b) {
        return f64::INFINITY;
    }
    let r = residue(a, b, freq);
    r.shared
        - (r.a_tokens + r.b_tokens) as f64 * EXTRA_TOKEN_BITS
        - (r.a_initials + r.b_initials) as f64 * EXTRA_INITIAL_BITS
}

/// Whether nothing in the two names contradicts: one side has nothing left once every match
/// is made ("X. H. Wu" and "Xiaohua Wu" are compatible; "Jared Siegel" and "Jerome Siegel",
/// or "R. Zhang" and "Bo Zhang", are not).
pub fn compatible(a: &Name, b: &Name, freq: &Freq) -> bool {
    let r = residue(a, b, freq);
    r.a_tokens + r.a_initials == 0 || r.b_tokens + r.b_initials == 0
}

/// What two names share, in bits, and what each has left once every match is made: tokens
/// (exact, joined, prefixed) and initials (the same initial, or an unmatched token's first
/// letter).
fn residue(a: &Name, b: &Name, freq: &Freq) -> Residue {
    let (mut shared, open) = matched(a, b, freq);
    let (mut a_init, mut b_init) = (a.initials.clone(), b.initials.clone());
    let same = take_matching(&mut a_init, &mut b_init);
    let mut a_first = open.firsts_a(a);
    let mut b_first = open.firsts_b(b);
    let a_abs = take_matching(&mut a_init, &mut b_first);
    let b_abs = take_matching(&mut b_init, &mut a_first);
    shared += (same + a_abs + b_abs) as f64 * INITIAL_MATCH_BITS;
    Residue {
        shared,
        a_tokens: a_first.len(),
        a_initials: a_init.len(),
        b_tokens: b_first.len(),
        b_initials: b_init.len(),
    }
}

/// The token matches of two names — exact, joined, prefixed — as the shared information they
/// carry and what is left unmatched on each side.
fn matched(a: &Name, b: &Name, freq: &Freq) -> (f64, Open) {
    let mut open = Open {
        a: vec![true; a.tokens.len()],
        b: vec![true; b.tokens.len()],
    };
    let mut shared = 0.0;
    for i in 0..a.tokens.len() {
        if let Some(j) = open.find_b(|j| b.tokens[j] == a.tokens[i]) {
            open.take(i, j);
            shared += freq.ic(token_hash(&a.tokens[i]));
        }
    }
    shared += joined(a, b, &mut open, freq);
    open.swap();
    shared += joined(b, a, &mut open, freq);
    open.swap();
    shared += prefixed(a, b, &mut open, freq);
    (shared, open)
}

/// A token of `a` written as two adjacent tokens of `b`.
fn joined(a: &Name, b: &Name, open: &mut Open, freq: &Freq) -> f64 {
    let mut shared = 0.0;
    for i in 0..a.tokens.len() {
        if !open.a[i] {
            continue;
        }
        let t = &a.tokens[i];
        let pair = (0..b.tokens.len().saturating_sub(1)).find(|&j| {
            open.b[j]
                && open.b[j + 1]
                && b.tokens[j].len() + b.tokens[j + 1].len() == t.len()
                && t.starts_with(b.tokens[j].as_str())
                && t.ends_with(b.tokens[j + 1].as_str())
        });
        if let Some(j) = pair {
            open.take(i, j);
            open.b[j + 1] = false;
            shared += freq.ic(token_hash(t));
        }
    }
    shared
}

/// A token of one name that begins a token of the other, credited with the shorter one's
/// information.
fn prefixed(a: &Name, b: &Name, open: &mut Open, freq: &Freq) -> f64 {
    let mut shared = 0.0;
    for i in 0..a.tokens.len() {
        if !open.a[i] {
            continue;
        }
        let t = &a.tokens[i];
        if let Some(j) = open.find_b(|j| begins(t, &b.tokens[j])) {
            open.take(i, j);
            let shorter = [t, &b.tokens[j]]
                .into_iter()
                .min_by_key(|s| s.len())
                .unwrap();
            shared += freq.ic(token_hash(shorter));
        }
    }
    shared
}

/// Whether the shorter of the two, at least three letters, begins the longer.
fn begins(x: &str, y: &str) -> bool {
    let (short, long) = if x.len() <= y.len() { (x, y) } else { (y, x) };
    short.chars().count() >= 3 && long.starts_with(short)
}

fn firsts(name: &Name, open: &[bool]) -> Vec<char> {
    name.tokens
        .iter()
        .zip(open)
        .filter(|(_, &o)| o)
        .filter_map(|(t, _)| t.chars().next())
        .collect()
}

pub fn same_person(a: &Name, b: &Name, freq: &Freq) -> bool {
    affinity(a, b, freq) >= MATCH_BITS
}

/// Reads the raw author table, derives the records and writes them with their manifest.
pub fn derive(stowage: &Stowage, names_table: Option<&Path>) -> io::Result<()> {
    let census = par_reduce::<Author, Census, _, _>(
        stowage,
        authors::C,
        MAIN_NAME,
        |acc, a| {
            acc.rows += 1;
            if let Some(name) = &a.display_name {
                acc.freq.add(name);
            }
            if let Some(code) = a.orcid.as_deref().and_then(orcid_code) {
                *acc.orcids.entry(code).or_default() += 1;
            }
        },
        |a, b| {
            a.rows += b.rows;
            a.freq.merge(b.freq);
            for (k, v) in b.orcids {
                *a.orcids.entry(k).or_default() += v;
            }
        },
        Some(10),
    );
    let multi: HashSet<OrcidCode> = census
        .orcids
        .iter()
        .filter(|(_, &n)| n > 1)
        .map(|(&c, _)| c)
        .collect();
    println!(
        "derive-ledger: {} author rows, {} ORCIDs on more than one record",
        census.rows,
        multi.len()
    );
    let wanted = std::sync::Arc::new(multi);
    let scan_wanted = std::sync::Arc::clone(&wanted);
    let mut recs = par_reduce::<Author, Vec<Rec>, _, _>(
        stowage,
        authors::C,
        MAIN_NAME,
        move |acc, a| {
            let (Some(id), Some(orcid)) = (a.get_parsed_id(), a.orcid.as_deref()) else {
                return;
            };
            if !orcid_code(orcid).is_some_and(|c| scan_wanted.contains(&c)) {
                return;
            }
            acc.push(Rec {
                orcid: normalize_orcid(orcid),
                id,
                name: Name::parse(a.display_name.as_deref().unwrap_or("")),
                works: a.works_count.unwrap_or(0),
            });
        },
        |a, b| a.extend(b),
        Some(10),
    );
    recs.sort_unstable_by(|a, b| (&a.orcid, a.id).cmp(&(&b.orcid, b.id)));
    let registered = match names_table {
        Some(path) => Some(load_registered(path, &wanted)?),
        None => None,
    };
    let mut manifest = DerivedManifest {
        author_rows: census.rows,
        orcids: wanted.len(),
        records: recs.len(),
        registered_names: registered.is_some(),
        ..Default::default()
    };
    let mut records = Vec::new();
    for group in recs.chunk_by(|a, b| a.orcid == b.orcid) {
        let names = registered
            .as_ref()
            .and_then(|r| orcid_code(&group[0].orcid).and_then(|c| r.get(&c)))
            .map(Vec::as_slice);
        records.extend(
            decide(group, names, &census.freq, &mut manifest)
                .into_iter()
                .map(|decision| Record {
                    orcid: group[0].orcid.clone(),
                    decision,
                }),
        );
    }
    write_records(&stowage.paths.user_ledger, &records, &manifest)?;
    println!(
        "derive-ledger: {} merges, {} strips → {DERIVED_JSONL}",
        manifest.merges.values().sum::<usize>(),
        manifest.strips.values().sum::<usize>()
    );
    Ok(())
}

/// The CLI entry: the registered-name table under the external data root, required when
/// `EXTERNAL_DATA_ROOT` names the root and optional under the default.
pub fn main(stowage: Stowage) -> io::Result<()> {
    let table = names_table_path()?;
    if table.is_none() {
        println!(
            "derive-ledger: no {NAMES_TABLE} under {DEFAULT_EXTERNAL_DATA_ROOT} — ORCID owners by most works only"
        );
    }
    derive(&stowage, table.as_deref())
}

fn names_table_path() -> io::Result<Option<PathBuf>> {
    let named = env::var_os(EXTERNAL_DATA_ROOT).filter(|v| !v.is_empty());
    let root = named
        .clone()
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(DEFAULT_EXTERNAL_DATA_ROOT));
    let path = root.join(NAMES_TABLE);
    match (path.exists(), named.is_some()) {
        (true, _) => Ok(Some(path)),
        (false, false) => Ok(None),
        (false, true) => Err(io::Error::new(
            io::ErrorKind::NotFound,
            format!(
                "{} missing — run `uv run -m pyscripts.orcid_summaries`",
                path.display()
            ),
        )),
    }
}

/// One ORCID's records: the over-bound ones stripped, the rest clustered by name, the owner
/// cluster merged into its oldest record, the other clusters stripped.
fn decide(
    group: &[Rec],
    registered: Option<&[Name]>,
    freq: &Freq,
    manifest: &mut DerivedManifest,
) -> Vec<Decision> {
    let mut out = Vec::new();
    let bound = WORK_SCREEN.max_author_papers;
    let (eligible, junk): (Vec<&Rec>, Vec<&Rec>) = group.iter().partition(|r| r.works <= bound);
    for r in junk {
        out.push(Decision::Strip {
            id: r.id,
            reason: Reason::OverWorkBound,
        });
        *manifest.strips.entry(Reason::OverWorkBound).or_default() += 1;
    }
    if eligible.is_empty() {
        return out;
    }
    let clusters = cluster(&eligible, freq);
    let (owner, reason) = owner(&clusters, &eligible, registered, freq);
    *manifest.owner_by.entry(reason).or_default() += 1;
    // Once the registered name has picked the owner, a cluster it does not contradict is the
    // holder's too: the registration is the evidence the names alone lacked. The oldest id of
    // everything merged keeps.
    let names = registered
        .filter(|_| reason == Reason::RegisteredName)
        .unwrap_or(&[]);
    let compatible_cluster = |members: &[usize]| {
        members
            .iter()
            .any(|&m| names.iter().any(|n| compatible(&eligible[m].name, n, freq)))
    };
    let reasons: Vec<Option<Reason>> = clusters
        .iter()
        .enumerate()
        .map(|(ci, members)| {
            if ci == owner {
                Some(reason)
            } else if compatible_cluster(members) {
                Some(Reason::CompatibleName)
            } else {
                None
            }
        })
        .collect();
    let keep = clusters
        .iter()
        .zip(&reasons)
        .filter(|(_, r)| r.is_some())
        .flat_map(|(members, _)| members.iter().map(|&m| eligible[m].id))
        .min()
        .unwrap();
    for (members, merge_reason) in clusters.iter().zip(reasons) {
        for &m in members {
            let id = eligible[m].id;
            match merge_reason {
                Some(_) if id == keep => {}
                Some(reason) => {
                    out.push(Decision::Merge {
                        drop: id,
                        keep,
                        reason,
                    });
                    *manifest.merges.entry(reason).or_default() += 1;
                }
                None => {
                    out.push(Decision::Strip {
                        id,
                        reason: Reason::NameMismatch,
                    });
                    *manifest.strips.entry(Reason::NameMismatch).or_default() += 1;
                }
            }
        }
    }
    out
}

/// Single-linkage clusters over `same_person`, each as sorted member indices.
fn cluster(recs: &[&Rec], freq: &Freq) -> Vec<Vec<usize>> {
    let mut parent: Vec<usize> = (0..recs.len()).collect();
    fn root(parent: &mut [usize], mut i: usize) -> usize {
        while parent[i] != i {
            parent[i] = parent[parent[i]];
            i = parent[i];
        }
        i
    }
    for i in 0..recs.len() {
        for j in i + 1..recs.len() {
            if same_person(&recs[i].name, &recs[j].name, freq) {
                let (ri, rj) = (root(&mut parent, i), root(&mut parent, j));
                if ri != rj {
                    parent[rj.max(ri)] = ri.min(rj);
                }
            }
        }
    }
    let mut by_root: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
    for i in 0..recs.len() {
        let r = root(&mut parent, i);
        by_root.entry(r).or_default().push(i);
    }
    by_root.into_values().collect()
}

/// The cluster a registered name matches best (ties to the most works), else the one with the
/// most works (ties to the oldest record).
fn owner(
    clusters: &[Vec<usize>],
    recs: &[&Rec],
    registered: Option<&[Name]>,
    freq: &Freq,
) -> (usize, Reason) {
    let works = |members: &[usize]| members.iter().map(|&m| recs[m].works as u64).sum::<u64>();
    let oldest = |members: &[usize]| members.iter().map(|&m| recs[m].id).min().unwrap();
    if let Some(names) = registered.filter(|n| !n.is_empty()) {
        let best = clusters
            .iter()
            .enumerate()
            .map(|(ci, members)| {
                let score = members
                    .iter()
                    .flat_map(|&m| names.iter().map(move |n| affinity(&recs[m].name, n, freq)))
                    .fold(f64::NEG_INFINITY, f64::max);
                (ci, score)
            })
            .filter(|&(_, s)| s >= MATCH_BITS)
            .max_by(|a, b| {
                a.1.total_cmp(&b.1)
                    .then_with(|| works(&clusters[a.0]).cmp(&works(&clusters[b.0])))
            });
        if let Some((ci, _)) = best {
            return (ci, Reason::RegisteredName);
        }
    }
    let ci = (0..clusters.len())
        .max_by(|&a, &b| {
            works(&clusters[a])
                .cmp(&works(&clusters[b]))
                .then_with(|| oldest(&clusters[b]).cmp(&oldest(&clusters[a])))
        })
        .unwrap();
    (ci, Reason::MostWorks)
}

/// The registered names of the wanted ORCIDs from the summaries table: given + family as one
/// name, the credit name and every other name as more.
fn load_registered(
    path: &Path,
    wanted: &HashSet<OrcidCode>,
) -> io::Result<HashMap<OrcidCode, Vec<Name>>> {
    let mut out: HashMap<OrcidCode, Vec<Name>> = HashMap::new();
    let reader = BufReader::new(zstd::Decoder::new(File::open(path)?)?);
    for line in reader.lines().skip(1) {
        let line = line?;
        let mut cells = line.split('\t');
        let Some(code) = cells.next().and_then(orcid_code) else {
            continue;
        };
        if !wanted.contains(&code) {
            continue;
        }
        let given = cells.next().unwrap_or("");
        let family = cells.next().unwrap_or("");
        let credit = cells.next().unwrap_or("");
        let others = cells.next().unwrap_or("");
        let names = out.entry(code).or_default();
        for raw in [format!("{given} {family}"), credit.to_string()]
            .into_iter()
            .chain(others.split('|').map(str::to_string))
        {
            let name = Name::parse(&raw);
            if !name.is_empty() && !names.contains(&name) {
                names.push(name);
            }
        }
    }
    println!(
        "derive-ledger: registered names for {} of {} ORCIDs",
        out.len(),
        wanted.len()
    );
    Ok(out)
}

/// One `active.jsonl`-shaped line per decision, in (ORCID, id) order, plus the manifest.
fn write_records(ul_dir: &Path, records: &[Record], manifest: &DerivedManifest) -> io::Result<()> {
    std::fs::create_dir_all(ul_dir)?;
    let mut out = BufWriter::new(File::create(ul_dir.join(DERIVED_JSONL))?);
    for Record { orcid, decision } in records {
        let line = match decision {
            Decision::Merge { drop, keep, reason } => serde_json::json!({
                "key": format!("{orcid}|merge_authors|{drop}"),
                "orcid": orcid,
                "kind": "merge_authors",
                "source": SOURCE,
                "reason": reason,
                "payload": {"kind": "merge_authors", "keep": {"oa_id": keep}, "drop": {"oa_id": drop}},
            }),
            Decision::Strip { id, reason } => serde_json::json!({
                "key": format!("{orcid}|strip_orcid|{id}"),
                "orcid": orcid,
                "kind": "strip_orcid",
                "source": SOURCE,
                "reason": reason,
                "payload": {"kind": "strip_orcid", "author": {"oa_id": id}},
            }),
        };
        serde_json::to_writer(&mut out, &line)?;
        out.write_all(b"\n")?;
    }
    out.flush()?;
    write_json(&ul_dir.join(DERIVED_MANIFEST), manifest)
}

/// The 16 ORCID digits (X = 10) as one base-11 number; None for anything else.
pub fn orcid_code(orcid: &str) -> Option<OrcidCode> {
    let mut code: u64 = 0;
    let mut n = 0;
    for c in normalize_orcid(orcid).chars() {
        let d = match c {
            '-' => continue,
            '0'..='9' => c as u64 - '0' as u64,
            'X' | 'x' => 10,
            _ => return None,
        };
        code = code * 11 + d;
        n += 1;
    }
    (n == 16).then_some(code)
}

/// Removes from `pool` one element equal to each of `items` it can find; returns the count.
fn take_matching(items: &mut Vec<char>, pool: &mut Vec<char>) -> usize {
    let mut matched = 0;
    items.retain(|c| match pool.iter().position(|p| p == c) {
        Some(p) => {
            pool.swap_remove(p);
            matched += 1;
            false
        }
        None => true,
    });
    matched
}

fn token_hash(tok: &str) -> u64 {
    let mut h = DefaultHasher::new();
    tok.hash(&mut h);
    h.finish()
}

/// Lowercase, with the Latin letters carrying diacritics or ligatures folded to ASCII.
pub fn fold(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars().flat_map(char::to_lowercase) {
        match fold_char(c) {
            Some(ascii) => out.push_str(ascii),
            None => out.push(c),
        }
    }
    squeeze(&out)
}

/// Drops an `e` after `a`, `o` or `u`, so the umlaut conventions meet: "gänsicke", "gaensicke"
/// and "gansicke" read alike, as do "müller", "mueller" and "muller".
fn squeeze(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut prev = ' ';
    for c in s.chars() {
        if !(c == 'e' && matches!(prev, 'a' | 'o' | 'u')) {
            out.push(c);
        }
        prev = c;
    }
    out
}

fn fold_char(c: char) -> Option<&'static str> {
    Some(match c {
        'à'..='å' | 'ā' | 'ă' | 'ą' => "a",
        'æ' => "ae",
        'ç' | 'ć' | 'ĉ' | 'ċ' | 'č' => "c",
        'ď' | 'đ' | 'ð' => "d",
        'è'..='ë' | 'ē' | 'ĕ' | 'ė' | 'ę' | 'ě' => "e",
        'ĝ' | 'ğ' | 'ġ' | 'ģ' => "g",
        'ĥ' | 'ħ' => "h",
        'ì'..='ï' | 'ĩ' | 'ī' | 'ĭ' | 'į' | 'ı' => "i",
        'ĳ' => "ij",
        'ĵ' => "j",
        'ķ' => "k",
        'ĺ' | 'ļ' | 'ľ' | 'ŀ' | 'ł' => "l",
        'ñ' | 'ń' | 'ņ' | 'ň' => "n",
        'ò'..='ö' | 'ø' | 'ō' | 'ŏ' | 'ő' => "o",
        'œ' => "oe",
        'ŕ' | 'ŗ' | 'ř' => "r",
        'ś' | 'ŝ' | 'ş' | 'š' | 'ș' | 'ſ' => "s",
        'ß' => "ss",
        'ţ' | 'ť' | 'ŧ' | 'ț' => "t",
        'þ' => "th",
        'ù'..='ü' | 'ũ' | 'ū' | 'ŭ' | 'ů' | 'ű' | 'ų' => "u",
        'ŵ' => "w",
        'ý' | 'ÿ' | 'ŷ' => "y",
        'ź' | 'ż' | 'ž' => "z",
        // combining marks, as a dotted capital I leaves behind when lowercased
        '\u{0300}'..='\u{036f}' => "",
        _ => return None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Token frequencies at the magnitudes of the full author table (some 3 × 10⁸ tokens):
    /// the most common names near 7 bits, common ones near 9, mid ones near 13, a rare one
    /// near 20 and an unseen one at 28.
    fn freq() -> Freq {
        let bands: [(&[&str], u32); 4] = [
            (
                &[
                    "john", "wei", "wang", "wu", "li", "lin", "dai", "chen", "zhang",
                ],
                2_000_000,
            ),
            (
                &["smith", "maria", "kevin", "von", "king", "ben", "stephen"],
                400_000,
            ),
            (&["watanabe", "kenji", "ranasinghe", "benjamin"], 40_000),
            (&["korff"], 300),
        ];
        Freq {
            counts: bands
                .iter()
                .flat_map(|(tokens, n)| tokens.iter().map(|t| (token_hash(t), *n)))
                .collect(),
            total: 1 << 28,
        }
    }

    fn same(a: &str, b: &str) -> bool {
        same_person(&Name::parse(a), &Name::parse(b), &freq())
    }

    #[test]
    fn rare_shared_names_absorb_extra_initials_common_ones_do_not() {
        assert!(same("Kevin Pelcomuchegler", "Kevin H. G. Pelcomuchegler"));
        assert!(!same("John Smith", "John H. G. Smith"));
        assert!(same("John Smith", "John Smith"));
        assert!(same("Wei Wang", "Wang Wei"));
        assert!(same("Wei Wang", "W. Wang"));
        assert!(same("Kenji Watanabe", "K. Watanabe"));
        assert!(same("J. R. Smith", "John R. Smith"));
    }

    #[test]
    fn different_people_under_one_orcid_stay_apart() {
        assert!(!same("Vidamor Cabannas", "Denivaldo Silva"));
        assert!(!same("Sasika Ranasinghe", "Indunil Ranasinghe"));
        assert!(!same("Wei Wang", "Lei Wang"));
        assert!(!same("A. Smith", "Jane Smith"));
        assert!(!same("10 PRIMO", "10 PHYSICS"));
    }

    #[test]
    fn transliteration_and_name_variants_match() {
        assert!(same("Anne Maaß", "Anne Maass"));
        assert!(same("Maria von Korff", "Maria von Korff Schmising"));
        assert!(same("Jean-Pierre Müller", "Jean Pierre Mueller"));
        assert!(same("Boris Gaensicke", "Boris T. Gänsicke"));
        assert_eq!(fold("Łukasz Żółć"), "lukasz zolc");
        assert_eq!(fold("Gänsicke"), fold("Gaensicke"));
        assert_eq!(fold("Ç. İşsever"), "c. issever");
    }

    #[test]
    fn a_registered_name_tells_compatible_clusters_from_contradicting_ones() {
        let f = freq();
        let ok = |a: &str, b: &str| compatible(&Name::parse(a), &Name::parse(b), &f);
        assert!(ok("X. Wu", "Xiaohua Wu"));
        assert!(ok("X. H. Wu", "Xiaohua Wu"));
        assert!(ok("S. Paredes", "Sandra R. Paredes Saenz"));
        assert!(ok("Split", "Sam Split"));
        assert!(ok("J. J. Chen", "Jing Chen"));
        assert!(!ok("Jerome H. Siegel", "Jared Siegel"));
        assert!(!ok("Ann Other", "Sam Split"));
        assert!(!ok("Zhiliang Huang", "Pu Hu"));
        assert!(!ok("R. Zhang", "Bo Zhang"));
        assert!(!ok("D. W. Young", "David R. Young"));
        assert!(!same("X. Wu", "X. H. Wu"), "the names alone stay apart");
    }

    #[test]
    fn spellings_of_one_name_match_and_short_common_ones_do_not() {
        assert!(same("Tieying Dai", "Tie-ying Dai"));
        assert!(same("Chen Xiang-Lei", "Xianglei Chen"));
        assert!(same("SP Hunger", "Stephen P. Hunger"));
        assert!(same("Ben King", "Benjamin King"));
        assert!(same("Mohammadmahdi Asgari", "Mohammad Mahdi Asgari"));
        assert!(!same("Li Wang", "Lin Wang"));
        assert!(!same("Andy Spakowitz", "Andrew J. Spakowitz"));
    }

    #[test]
    fn owner_by_registered_name_else_most_works() {
        let f = freq();
        let rec = |id, name: &str, works| Rec {
            orcid: "0000-0001-0000-0001".into(),
            id,
            name: Name::parse(name),
            works,
        };
        let recs = vec![
            rec(3, "Sam Split", 5),
            rec(1, "S. Split", 2),
            rec(2, "Ann Other", 50),
        ];
        let refs: Vec<&Rec> = recs.iter().collect();
        let clusters = cluster(&refs, &f);
        assert_eq!(clusters, vec![vec![0, 1], vec![2]]);
        let registered = [Name::parse("Samuel Split")];
        assert_eq!(
            owner(&clusters, &refs, Some(&registered), &f),
            (0, Reason::RegisteredName)
        );
        assert_eq!(owner(&clusters, &refs, None, &f), (1, Reason::MostWorks));
        assert_eq!(
            owner(&clusters, &refs, Some(&[Name::parse("Nobody Here")]), &f),
            (1, Reason::MostWorks)
        );
    }

    #[test]
    fn a_group_decides_into_merges_and_strips() {
        let f = freq();
        let rec = |id, name: &str, works| Rec {
            orcid: "0000-0001-0000-0001".into(),
            id,
            name: Name::parse(name),
            works,
        };
        let group = vec![
            rec(10, "Sam Split", 5),
            rec(11, "S. Split", 2),
            rec(12, "Ann Other", 3),
            rec(13, "Sam Split", WORK_SCREEN.max_author_papers + 1),
        ];
        let mut manifest = DerivedManifest::default();
        let mut merges = Vec::new();
        let mut strips = Vec::new();
        for d in decide(&group, None, &f, &mut manifest) {
            match d {
                Decision::Merge { drop, keep, reason } => merges.push((drop, keep, reason)),
                Decision::Strip { id, reason } => strips.push((id, reason)),
            }
        }
        assert_eq!(merges, vec![(11, 10, Reason::MostWorks)]);
        strips.sort_unstable();
        assert_eq!(
            strips,
            vec![(12, Reason::NameMismatch), (13, Reason::OverWorkBound)]
        );
        assert_eq!(manifest.owner_by[&Reason::MostWorks], 1);
    }

    #[test]
    fn a_compatible_cluster_merges_only_under_a_registered_owner() {
        let f = freq();
        let rec = |id, name: &str, works| Rec {
            orcid: "0000-0001-0000-0001".into(),
            id,
            name: Name::parse(name),
            works,
        };
        // "Li" alone contradicts neither record but picks no owner, so the most works do;
        // the compatible cluster is then not the owner's and keeps out.
        let group = vec![rec(10, "Jun Li", 5), rec(11, "Ann Other", 50)];
        let mut manifest = DerivedManifest::default();
        let decisions = decide(&group, Some(&[Name::parse("Li")]), &f, &mut manifest);
        assert_eq!(
            decisions,
            vec![Decision::Strip {
                id: 10,
                reason: Reason::NameMismatch
            }]
        );
        assert_eq!(manifest.owner_by[&Reason::MostWorks], 1);
    }

    #[test]
    fn orcid_codes_are_unique_and_total() {
        assert_eq!(
            orcid_code("https://orcid.org/0000-0002-8804-4520"),
            orcid_code("0000-0002-8804-4520")
        );
        assert_ne!(
            orcid_code("0000-0002-8804-4520"),
            orcid_code("0000-0002-8804-452X")
        );
        assert!(orcid_code("0000-0002-8804-452").is_none());
        assert!(orcid_code("not an orcid").is_none());
    }
}
