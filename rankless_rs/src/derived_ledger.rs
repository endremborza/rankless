//! `derive-ledger`: the identity records OpenAlex's author split implies, written in the ledger's
//! own format as one more source (`user-ledger/derived.jsonl`). The author records sharing an
//! ORCID are one person's unless their names say otherwise: each ORCID's records are clustered by
//! name; the cluster the ORCID's registered name matches (else the one with the most works) owns
//! it; the owner's oldest record keeps; every other record of the ORCID is merged into the keep or
//! stripped of the ORCID. A record over the author screen's work bound never owns or keeps. A
//! person merged from several records is named by the registered name, else by their largest
//! record, when that name is fuller than the keep's own.

use std::{
    borrow::Cow,
    cmp::Reverse,
    collections::BTreeMap,
    env,
    fs::File,
    hash::{DefaultHasher, Hash, Hasher},
    io::{self, BufRead, BufReader, BufWriter, Write},
    path::{Path, PathBuf},
};

use deunicode::deunicode;
use dmove::BigId;
use hashbrown::{HashMap, HashSet};
use serde::Serialize;
use serde_json::{json, Value};
use wiretypes::wire;

use crate::{
    common::{ParsedId, Stowage, MAIN_NAME},
    csv_iter::par_reduce,
    csv_writers::authors,
    metrics::WORK_SCREEN,
    oa_structs::post::Author,
    user_ledger::{normalize_orcid, write_json, DERIVED_JSONL, DERIVED_MANIFEST},
};

/// The env var naming the root of the data from outside OpenAlex.
#[wire]
pub const EXTERNAL_DATA_ROOT: &str = "EXTERNAL_DATA_ROOT";
/// The root when the variable is unset: a dev box, relative to the repo root the pipeline runs from.
#[wire]
pub const DEFAULT_EXTERNAL_DATA_ROOT: &str = "data/external";
/// The ORCID registry's names, under the root.
#[wire]
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
/// What a variant match (two forms of one given name, or two tokens one edit apart) is credited
/// below the exact match of its more common token: a variant is about a quarter as likely to
/// be the same name, so it never outscores an exact match of either side.
const VARIANT_DISCOUNT_BITS: f64 = 2.0;
/// The shortest token a one-edit variant is read at; shorter names one edit apart are mostly
/// different names ("li" ~ "lin", "wei" ~ "lei").
const MIN_EDIT_LEN: usize = 6;
/// The information the rarer of two tokens one edit apart needs to be a misspelling of the
/// other ("kaniska" ~ "kanishka"); below it both are names of their own ("christian" ~
/// "christina", "gerald" ~ "gerard", "akihiko" ~ "akihito").
const TYPO_BITS: f64 = 20.0;
/// Full tokens a registered name needs to vouch for a cluster the names alone keep apart:
/// "X WU" or "G. LI" fits too many people.
const MIN_VOUCHING_TOKENS: usize = 2;
/// Capital blocks per name read both ways; a name with more reads them as initials only.
const MAX_CAPS: usize = 3;
/// Diminutives and spellings of a given name, each with the name it stands for, as folded
/// tokens sorted by the first; one may stand for several names, and the spellings of one
/// name all stand for the same one ("mohamed", "mohammed" → "muhammad").
static NICKNAMES: &[(&str, &str)] = &[
    ("abby", "abigail"),
    ("achim", "joachim"),
    ("alexandre", "alexander"),
    ("andy", "andreas"),
    ("andy", "andrew"),
    ("angie", "angela"),
    ("annie", "anna"),
    ("annie", "anne"),
    ("anya", "anna"),
    ("bartek", "bartlomiej"),
    ("bas", "sebastiaan"),
    ("basia", "barbara"),
    ("becky", "rebecca"),
    ("beppe", "giuseppe"),
    ("bernard", "bernhard"),
    ("bernd", "bernhard"),
    ("beth", "elisabeth"),
    ("beth", "elizabeth"),
    ("beto", "alberto"),
    ("beto", "roberto"),
    ("betta", "elisabetta"),
    ("betty", "elizabeth"),
    ("bice", "beatrice"),
    ("bill", "william"),
    ("billy", "william"),
    ("bob", "robert"),
    ("bobby", "robert"),
    ("borya", "boris"),
    ("bram", "abraham"),
    ("cathy", "catherine"),
    ("cees", "cornelis"),
    ("charlie", "charles"),
    ("charo", "rosario"),
    ("checco", "francesco"),
    ("chelo", "consulo"),
    ("chema", "jose"),
    ("chet", "chester"),
    ("chucho", "jesus"),
    ("chuck", "charles"),
    ("chus", "jesus"),
    ("chuy", "jesus"),
    ("ciccio", "francesco"),
    ("cindy", "cynthia"),
    ("claus", "nikolaus"),
    ("concha", "concepcion"),
    ("conchi", "concepcion"),
    ("curro", "francisco"),
    ("danny", "daniel"),
    ("dave", "david"),
    ("davy", "david"),
    ("debbie", "deborah"),
    ("dick", "richard"),
    ("dima", "dmitri"),
    ("dima", "dmitriy"),
    ("dima", "dmitry"),
    ("dimitris", "dimitrios"),
    ("dirk", "diederik"),
    ("eddie", "edward"),
    ("ellie", "eleanor"),
    ("els", "elisabeth"),
    ("enzo", "lorenzo"),
    ("enzo", "vincenzo"),
    ("evgenii", "evgeny"),
    ("evgeniy", "evgeny"),
    ("fedya", "fyodor"),
    ("franco", "francesco"),
    ("franek", "franciszek"),
    ("frank", "francis"),
    ("freddie", "frederick"),
    ("fritz", "friedrich"),
    ("gabi", "gabriele"),
    ("galya", "galina"),
    ("gene", "eugene"),
    ("gerd", "gerhard"),
    ("gerrit", "gerard"),
    ("gerrit", "gerardus"),
    ("gerry", "gerald"),
    ("gerry", "gerard"),
    ("gert", "gerardus"),
    ("gert", "gerhard"),
    ("gianni", "giovanni"),
    ("gigi", "luigi"),
    ("ginny", "virginia"),
    ("gino", "luigi"),
    ("giusi", "giuseppina"),
    ("gosha", "georgy"),
    ("gosia", "malgorzata"),
    ("grisha", "grigory"),
    ("guus", "augustus"),
    ("hal", "harold"),
    ("hal", "henry"),
    ("hank", "henry"),
    ("hanneke", "johanna"),
    ("hannes", "johannes"),
    ("hans", "johann"),
    ("hans", "johannes"),
    ("harm", "hermanus"),
    ("harry", "harold"),
    ("harry", "henry"),
    ("hein", "hendrik"),
    ("heinz", "heinrich"),
    ("henk", "hendrik"),
    ("honza", "jan"),
    ("jaap", "jacob"),
    ("jaap", "jacobus"),
    ("jack", "john"),
    ("jake", "jacob"),
    ("jamie", "james"),
    ("jan", "johannes"),
    ("jaquline", "jacquline"),
    ("jarek", "jaroslaw"),
    ("jeff", "geoffrey"),
    ("jeffery", "geoffrey"),
    ("jeffrey", "geoffrey"),
    ("jenny", "jennifer"),
    ("jerry", "gerald"),
    ("jim", "james"),
    ("jimmy", "james"),
    ("jirka", "jiri"),
    ("jo", "joseph"),
    ("jochen", "joachim"),
    ("joke", "johanna"),
    ("jon", "john"),
    ("jonathon", "jonathan"),
    ("joop", "johannes"),
    ("joost", "justus"),
    ("jorg", "georg"),
    ("jupp", "josef"),
    ("jurek", "jerzy"),
    ("kasia", "katarzyna"),
    ("kate", "catherine"),
    ("kate", "katherine"),
    ("kate", "kathryn"),
    ("kathe", "katharina"),
    ("katherine", "catherine"),
    ("kathi", "katharina"),
    ("kathryn", "catherine"),
    ("kathy", "katherine"),
    ("kathy", "kathryn"),
    ("katie", "catherine"),
    ("katie", "katherine"),
    ("katya", "ekaterina"),
    ("katya", "yekaterina"),
    ("kees", "cornelis"),
    ("kees", "cornelius"),
    ("kenny", "kenneth"),
    ("kike", "enriqu"),
    ("klaas", "nicolaas"),
    ("klaus", "nicolaus"),
    ("klaus", "nikolaus"),
    ("kolya", "nikolai"),
    ("koos", "jacobus"),
    ("kostya", "konstantin"),
    ("kuba", "jakub"),
    ("kurt", "konrad"),
    ("larry", "laurence"),
    ("larry", "lawrence"),
    ("lele", "emanule"),
    ("len", "leonard"),
    ("lena", "elena"),
    ("lena", "helena"),
    ("lene", "helene"),
    ("leni", "helene"),
    ("lenny", "leonard"),
    ("liam", "william"),
    ("libby", "elizabeth"),
    ("lies", "elisabeth"),
    ("liesbeth", "elisabeth"),
    ("liesel", "elisabeth"),
    ("liz", "elisabeth"),
    ("liz", "elizabeth"),
    ("lizzie", "elizabeth"),
    ("lola", "dolores"),
    ("lucho", "luis"),
    ("lupe", "guadalupe"),
    ("lutz", "ludwig"),
    ("maggie", "margaret"),
    ("mandy", "amanda"),
    ("manolo", "manul"),
    ("masha", "maria"),
    ("mathew", "matthew"),
    ("meg", "margaret"),
    ("memo", "guillermo"),
    ("micheal", "michal"),
    ("mick", "michal"),
    ("mieke", "maria"),
    ("mike", "michal"),
    ("mikey", "michal"),
    ("mimmo", "domenico"),
    ("misha", "michal"),
    ("misha", "mikhail"),
    ("mohamed", "muhammad"),
    ("mohammad", "muhammad"),
    ("mohammed", "muhammad"),
    ("molly", "mary"),
    ("nacho", "ignacio"),
    ("nadya", "nadezhda"),
    ("nando", "ferdinando"),
    ("nando", "fernando"),
    ("nanni", "giovanni"),
    ("natalya", "natalia"),
    ("natasha", "natalia"),
    ("natasha", "natalya"),
    ("nate", "nathan"),
    ("nate", "nathaniel"),
    ("ned", "edward"),
    ("nell", "eleanor"),
    ("nick", "nicholas"),
    ("nick", "nicolas"),
    ("nick", "nikolaos"),
    ("nicolas", "nicholas"),
    ("olivier", "oliver"),
    ("ollie", "oliver"),
    ("olya", "olga"),
    ("ondra", "ondrej"),
    ("paco", "francisco"),
    ("pancha", "francisca"),
    ("pancho", "francisco"),
    ("pasha", "pavel"),
    ("patty", "patricia"),
    ("peggy", "margaret"),
    ("pepe", "jose"),
    ("peppe", "giuseppe"),
    ("petya", "pyotr"),
    ("phillip", "philip"),
    ("pili", "pilar"),
    ("pina", "giuseppina"),
    ("pino", "giuseppe"),
    ("pippo", "filippo"),
    ("polly", "mary"),
    ("quiqu", "enriqu"),
    ("rachal", "rachel"),
    ("renzo", "lorenzo"),
    ("resi", "theresia"),
    ("rick", "richard"),
    ("ricky", "richard"),
    ("rien", "marinus"),
    ("rike", "friederike"),
    ("rinus", "marinus"),
    ("robbie", "robert"),
    ("ronnie", "ronald"),
    ("rudi", "rudolf"),
    ("rudy", "rudolph"),
    ("ruud", "rudolf"),
    ("ruud", "rudolph"),
    ("sacha", "alexander"),
    ("sally", "sarah"),
    ("sander", "alexander"),
    ("sandro", "alessandro"),
    ("sandy", "sandra"),
    ("sasha", "aleksandr"),
    ("sasha", "alexander"),
    ("sasha", "alexandra"),
    ("sasha", "oleksandr"),
    ("sebastien", "sebastian"),
    ("sepp", "josef"),
    ("slava", "vladislav"),
    ("slava", "vyacheslav"),
    ("staszek", "stanislaw"),
    ("steffi", "stefanie"),
    ("steve", "stephen"),
    ("steven", "stephen"),
    ("susie", "susan"),
    ("tanya", "tatiana"),
    ("tanya", "tatyana"),
    ("ted", "edward"),
    ("ted", "theodore"),
    ("terry", "terence"),
    ("terry", "terrence"),
    ("tess", "theresa"),
    ("tessa", "theresa"),
    ("teun", "antonius"),
    ("thijs", "matthijs"),
    ("tolya", "anatoly"),
    ("tom", "thomas"),
    ("tomek", "tomasz"),
    ("tommy", "thomas"),
    ("ton", "antonius"),
    ("toni", "anton"),
    ("toni", "antonio"),
    ("tono", "antonio"),
    ("tony", "anthony"),
    ("tony", "antonio"),
    ("tony", "antonios"),
    ("toon", "antonius"),
    ("tori", "victoria"),
    ("tricia", "patricia"),
    ("trish", "patricia"),
    ("uli", "ulrich"),
    ("ulli", "ulrich"),
    ("valya", "valentina"),
    ("vanni", "giovanni"),
    ("vanya", "ivan"),
    ("vicki", "victoria"),
    ("vicky", "victoria"),
    ("volodya", "vladimir"),
    ("vova", "vladimir"),
    ("willi", "wilhelm"),
    ("wim", "willem"),
    ("wojtek", "wojciech"),
    ("yura", "yuri"),
    ("yura", "yuriy"),
    ("zack", "zachary"),
    ("zackary", "zachary"),
    ("zhenya", "evgeny"),
    ("zhenya", "yevgeny"),
    ("zosia", "zofia"),
];

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
    pub names: BTreeMap<Reason, usize>,
}

/// A name as compared: full tokens transliterated to lowercase ASCII, in the order written,
/// with their sorted hashes for the identity test; initials apart, sorted. A raw token of two
/// or three capitals ("HG", "LI") is that many initials, and also kept in `caps` for the
/// readings that take it as a name token.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Name {
    tokens: Vec<String>,
    sorted: Vec<u64>,
    initials: Vec<char>,
    caps: Vec<String>,
}

/// Token frequencies over every author name, for the information content of a shared token.
#[derive(Default)]
pub struct Freq {
    counts: HashMap<u64, u32>,
    total: u64,
}

/// An ORCID's registered names, and its given and family name as one display form.
#[derive(Default)]
struct Registered {
    names: Vec<Name>,
    display: String,
}

struct Rec {
    orcid: String,
    id: BigId,
    name: Name,
    display: String,
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

/// Why a record is merged (how its ORCID's owner cluster was chosen) or stripped, and where a
/// keep's name comes from.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Reason {
    RegisteredName,
    MostWorks,
    /// A cluster outside the owner's that no registered name contradicts.
    CompatibleName,
    NameMismatch,
    OverWorkBound,
    /// The display name of the owner cluster's record with the most works.
    LargestRecord,
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
    Name {
        keep: BigId,
        name: String,
        reason: Reason,
    },
}

impl Name {
    pub fn parse(raw: &str) -> Self {
        let (mut tokens, mut initials, mut caps) = (Vec::new(), Vec::new(), Vec::new());
        for raw_tok in deunicode(raw)
            .split(|c: char| !c.is_ascii_alphanumeric())
            .filter(|t| !t.is_empty())
        {
            if raw_tok.bytes().all(|c| c.is_ascii_digit()) {
                continue;
            }
            let tok = squeeze(raw_tok);
            if tok.len() == 1 {
                initials.extend(tok.chars());
            } else if raw_tok.len() <= 3 && raw_tok.bytes().all(|c| c.is_ascii_uppercase()) {
                initials.extend(tok.chars());
                caps.push(tok);
            } else {
                tokens.push(tok);
            }
        }
        initials.sort_unstable();
        Self::new(tokens, initials, caps)
    }

    fn new(tokens: Vec<String>, initials: Vec<char>, caps: Vec<String>) -> Self {
        let mut sorted: Vec<u64> = tokens.iter().map(|t| token_hash(t)).collect();
        sorted.sort_unstable();
        Self {
            tokens,
            sorted,
            initials,
            caps,
        }
    }

    fn is_empty(&self) -> bool {
        self.tokens.is_empty() && self.initials.is_empty()
    }

    /// The name with each capital block as initials, then with every subset of them read as
    /// name tokens instead ("Wei LI" is also "Wei Li"); each reading is unambiguous.
    fn readings(&self) -> impl Iterator<Item = Cow<'_, Name>> {
        let n = if self.caps.len() <= MAX_CAPS {
            self.caps.len()
        } else {
            0
        };
        (0..1u32 << n).map(move |mask| match n {
            0 => Cow::Borrowed(self),
            _ => Cow::Owned(self.read_caps(mask)),
        })
    }

    /// The reading with the capital blocks in `mask` as tokens.
    fn read_caps(&self, mask: u32) -> Self {
        let (mut tokens, mut initials) = (self.tokens.clone(), self.initials.clone());
        for (i, block) in self.caps.iter().enumerate() {
            if mask & (1 << i) != 0 {
                for c in block.chars() {
                    let at = initials.iter().position(|&x| x == c).unwrap();
                    initials.remove(at);
                }
                tokens.push(block.clone());
            }
        }
        Self::new(tokens, initials, Vec::new())
    }

    /// The reading closest to any of `names`, the base one on ties, with its affinity to the
    /// closest: what the name means beside them ("ROY PARKER" beside "Roy Parker" is no set of
    /// initials).
    fn read_beside(&self, names: &[&Name], freq: &Freq) -> (Name, f64) {
        let closest = |r: &Name| {
            names
                .iter()
                .map(|n| affinity(n, r, freq))
                .fold(f64::NEG_INFINITY, f64::max)
        };
        let (score, reading) = self
            .readings()
            .map(|r| (closest(&r), r))
            .reduce(|best, r| if r.0 > best.0 { r } else { best })
            .unwrap();
        (reading.into_owned(), score)
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

impl Decision {
    /// The decision as one `active.jsonl`-shaped line of the derived source.
    fn line(&self, orcid: &str) -> Value {
        let (key, kind, reason, mut payload) = match self {
            Decision::Merge { drop, keep, reason } => (
                format!("{orcid}|merge_authors|{drop}"),
                "merge_authors",
                reason,
                json!({"keep": {"oa_id": keep}, "drop": {"oa_id": drop}}),
            ),
            Decision::Strip { id, reason } => (
                format!("{orcid}|strip_orcid|{id}"),
                "strip_orcid",
                reason,
                json!({"author": {"oa_id": id}}),
            ),
            Decision::Name { keep, name, reason } => (
                format!("{keep}|name_author|"),
                "name_author",
                reason,
                json!({"author": {"oa_id": keep}, "name": name}),
            ),
        };
        payload["kind"] = kind.into();
        json!({
            "key": key,
            "orcid": orcid,
            "kind": kind,
            "source": SOURCE,
            "reason": reason,
            "payload": payload,
        })
    }
}

/// Shared minus unshared name information in bits, over the best pairing of the two names'
/// readings; identical names are infinitely alike. A token matches the same token, one
/// written as two adjacent tokens ("xianglei" ~ "xiang lei"), one it begins ("ben" ~
/// "benjamin") or a variant (`variant`); an initial matches the same initial or the first
/// letter of an otherwise unmatched token.
pub fn affinity(a: &Name, b: &Name, freq: &Freq) -> f64 {
    over_readings(a, b, f64::NEG_INFINITY, |best, a, b| {
        if a.alike(b) {
            return f64::INFINITY;
        }
        let r = residue(a, b, freq);
        best.max(
            r.shared
                - (r.a_tokens + r.b_tokens) as f64 * EXTRA_TOKEN_BITS
                - (r.a_initials + r.b_initials) as f64 * EXTRA_INITIAL_BITS,
        )
    })
}

/// Whether the record name `rec` and the registered name `reg` do not contradict each other
/// under some reading: once every match is made (tokens, initials, an initial against a token's
/// first letter), one side has nothing left. What the other side still has is allowed, so
/// "X. H. Wu" fits "Xiao-Hua Wu" and "Xiaohua Wu" fits "Xiaohua Q. Wu"; a record initial the
/// registration does not explain is tolerated as long as the registration is used up.
pub fn compatible(rec: &Name, reg: &Name, freq: &Freq) -> bool {
    over_readings(rec, reg, false, |ok, rec, reg| {
        ok || {
            let r = residue(rec, reg, freq);
            r.a_tokens + r.a_initials == 0 || r.b_tokens + r.b_initials == 0
        }
    })
}

/// `f` folded over every pairing of the two names' readings.
fn over_readings<T>(a: &Name, b: &Name, init: T, mut f: impl FnMut(T, &Name, &Name) -> T) -> T {
    let mut acc = init;
    for ra in a.readings() {
        for rb in b.readings() {
            acc = f(acc, &ra, &rb);
        }
    }
    acc
}

/// What two names share, in bits, and what each has left once every match is made: tokens
/// (exact, joined, prefixed, variant) and initials (the same initial, or an unmatched token's
/// first letter).
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

/// The token matches of two names — exact, joined, prefixed, variant — as the shared
/// information they carry and what is left unmatched on each side.
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
    shared += variants(a, b, &mut open, freq);
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

/// A token of one name that is a variant of a token of the other, credited with the more
/// common one's information less `VARIANT_DISCOUNT_BITS`.
fn variants(a: &Name, b: &Name, open: &mut Open, freq: &Freq) -> f64 {
    let mut shared = 0.0;
    for i in 0..a.tokens.len() {
        if !open.a[i] {
            continue;
        }
        let t = &a.tokens[i];
        if let Some(j) = open.find_b(|j| variant(t, &b.tokens[j], freq)) {
            open.take(i, j);
            let ic = freq
                .ic(token_hash(t))
                .min(freq.ic(token_hash(&b.tokens[j])));
            shared += (ic - VARIANT_DISCOUNT_BITS).max(0.0);
        }
    }
    shared
}

/// Two forms of one given name ("andy" ~ "andrew", "kees" ~ "cees"), or two tokens of
/// `MIN_EDIT_LEN` letters or more one substitution, insertion, deletion or adjacent
/// transposition apart ("tinging" ~ "tingting"), the rarer of them `TYPO_BITS` or more.
fn variant(x: &str, y: &str, freq: &Freq) -> bool {
    forms(x).any(|f| forms(y).any(|g| f == g))
        || (one_edit(x.as_bytes(), y.as_bytes())
            && freq.ic(token_hash(x)).max(freq.ic(token_hash(y))) >= TYPO_BITS)
}

/// The token and the names it is a diminutive or a spelling of.
fn forms(tok: &str) -> impl Iterator<Item = &str> {
    let from = NICKNAMES.partition_point(|&(n, _)| n < tok);
    let to = from + NICKNAMES[from..].partition_point(|&(n, _)| n == tok);
    std::iter::once(tok).chain(NICKNAMES[from..to].iter().map(|&(_, full)| full))
}

fn one_edit(x: &[u8], y: &[u8]) -> bool {
    let (short, long) = if x.len() <= y.len() { (x, y) } else { (y, x) };
    if short.len() < MIN_EDIT_LEN || long.len() - short.len() > 1 {
        return false;
    }
    let p = short.iter().zip(long).take_while(|(a, b)| a == b).count();
    if p == short.len() {
        return short.len() != long.len();
    }
    if short.len() < long.len() {
        return short[p..] == long[p + 1..];
    }
    short[p + 1..] == long[p + 1..]
        || (short[p] == long[p + 1] && short[p + 1] == long[p] && short[p + 2..] == long[p + 2..])
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
            let display = a.display_name.clone().unwrap_or_default();
            acc.push(Rec {
                orcid: normalize_orcid(orcid),
                id,
                name: Name::parse(&display),
                display,
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
        let reg = registered
            .as_ref()
            .and_then(|r| orcid_code(&group[0].orcid).and_then(|c| r.get(&c)));
        records.extend(
            decide(group, reg, &census.freq, &mut manifest)
                .into_iter()
                .map(|decision| Record {
                    orcid: group[0].orcid.clone(),
                    decision,
                }),
        );
    }
    write_records(&stowage.paths.user_ledger, &records, &manifest)?;
    println!(
        "derive-ledger: {} merges, {} strips, {} names → {DERIVED_JSONL}",
        manifest.merges.values().sum::<usize>(),
        manifest.strips.values().sum::<usize>(),
        manifest.names.values().sum::<usize>()
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
            format!("{} missing — run `make orcid_summaries`", path.display()),
        )),
    }
}

/// One ORCID's records: the over-bound ones stripped, the rest clustered by name, the owner
/// cluster merged into its oldest record, the other clusters stripped; a keep that absorbs
/// records takes the name `keep_name` chooses.
fn decide(
    group: &[Rec],
    registered: Option<&Registered>,
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
    let names = registered.map(|r| r.names.as_slice());
    let (owner, reason) = owner(&clusters, &eligible, names, freq);
    *manifest.owner_by.entry(reason).or_default() += 1;
    // Once the registered name has picked the owner, a cluster it does not contradict is the
    // holder's too: the registration, read as the owner's names read it, is the evidence the
    // names alone lacked. Only a registered name of `MIN_VOUCHING_TOKENS` full tokens vouches,
    // and none does unless one of them names the owner. The oldest id of everything merged
    // keeps.
    let owners: Vec<&Rec> = clusters[owner].iter().map(|&m| eligible[m]).collect();
    let owner_names: Vec<&Name> = owners.iter().map(|r| &r.name).collect();
    let read: Vec<(Name, f64)> = names
        .filter(|_| reason == Reason::RegisteredName)
        .unwrap_or(&[])
        .iter()
        .map(|n| n.read_beside(&owner_names, freq))
        .collect();
    let vouches = |n: &Name| n.tokens.len() >= MIN_VOUCHING_TOKENS;
    let vouching = read
        .iter()
        .any(|(n, closeness)| *closeness >= MATCH_BITS && vouches(n));
    let names: Vec<&Name> = read
        .iter()
        .map(|(n, _)| n)
        .filter(|n| vouching && vouches(n))
        .collect();
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
        .flat_map(|(members, _)| members.iter().map(|&m| eligible[m]))
        .min_by_key(|r| r.id)
        .unwrap();
    let mut merged = false;
    for (members, merge_reason) in clusters.iter().zip(reasons) {
        for &m in members {
            let id = eligible[m].id;
            match merge_reason {
                Some(_) if id == keep.id => {}
                Some(reason) => {
                    out.push(Decision::Merge {
                        drop: id,
                        keep: keep.id,
                        reason,
                    });
                    *manifest.merges.entry(reason).or_default() += 1;
                    merged = true;
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
    if !merged {
        return out;
    }
    let display = registered.map(|r| r.display.as_str());
    if let Some((name, reason)) = keep_name(&owners, keep, display, freq) {
        out.push(Decision::Name {
            keep: keep.id,
            name,
            reason,
        });
        *manifest.names.entry(reason).or_default() += 1;
    }
    out
}

/// The name a person merged from several records shows: of the registered given and family
/// name (when `presentable` and one of the owner's names) and the display name of the owner's
/// record with the most works, the one with the most full tokens, ties in that order; None
/// unless it has more than the keep's own, so a keep's initials and diacritics stay.
fn keep_name(
    owners: &[&Rec],
    keep: &Rec,
    registered: Option<&str>,
    freq: &Freq,
) -> Option<(String, Reason)> {
    let largest = owners
        .iter()
        .max_by_key(|r| (r.works, Reverse(r.id)))
        .unwrap();
    let registered = registered
        .filter(|d| presentable(d))
        .map(|d| (d, Name::parse(d)))
        .filter(|(_, n)| owners.iter().any(|r| same_person(&r.name, n, freq)))
        .map(|(d, n)| (d, n.tokens.len(), Reason::RegisteredName));
    let largest = (
        largest.display.as_str(),
        largest.name.tokens.len(),
        Reason::LargestRecord,
    );
    let (name, full, reason) = registered
        .into_iter()
        .chain([largest])
        .reduce(|best, c| if c.1 > best.1 { c } else { best })
        .unwrap();
    (full > keep.name.tokens.len()).then(|| (name.to_string(), reason))
}

/// Written in Latin script, in two tokens or more, and neither all lowercase nor all capitals.
fn presentable(name: &str) -> bool {
    let latin = |c: char| {
        !c.is_alphabetic()
            || c.is_ascii()
            || matches!(c, '\u{c0}'..='\u{24f}' | '\u{1e00}'..='\u{1eff}')
    };
    name.chars().all(latin)
        && name.split_whitespace().nth(1).is_some()
        && name.chars().any(char::is_uppercase)
        && name.chars().any(char::is_lowercase)
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
/// name and the display form, the credit name and every other name as more.
fn load_registered(
    path: &Path,
    wanted: &HashSet<OrcidCode>,
) -> io::Result<HashMap<OrcidCode, Registered>> {
    let mut out: HashMap<OrcidCode, Registered> = HashMap::new();
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
        let reg = out.entry(code).or_default();
        let full = format!("{} {}", given.trim(), family.trim());
        if reg.display.is_empty() {
            reg.display = full.trim().to_string();
        }
        for raw in [full.as_str(), credit].into_iter().chain(others.split('|')) {
            let name = Name::parse(raw);
            if !name.is_empty() && !reg.names.contains(&name) {
                reg.names.push(name);
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
        serde_json::to_writer(&mut out, &decision.line(orcid))?;
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

/// Transliterated to ASCII (Latin diacritics and ligatures folded, other scripts romanized),
/// then `squeeze`d.
pub fn fold(s: &str) -> String {
    squeeze(&deunicode(s))
}

/// Lowercase ASCII with an `e` after `a`, `o` or `u` dropped, so the umlaut conventions meet:
/// "gänsicke", "gaensicke" and "gansicke" read alike, as do "müller", "mueller" and "muller".
fn squeeze(ascii: &str) -> String {
    let mut out = String::with_capacity(ascii.len());
    let mut prev = ' ';
    for c in ascii.chars().map(|c| c.to_ascii_lowercase()) {
        if !(c == 'e' && matches!(prev, 'a' | 'o' | 'u')) {
            out.push(c);
        }
        prev = c;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Token frequencies at the magnitudes of the full author table (some 3 × 10⁸ tokens):
    /// the most common names near 7 bits, common ones near 9, 11 and 13, a rarer one at 16,
    /// rare ones near 20 and 21 and an unseen one at 28.
    fn freq() -> Freq {
        let bands: [(&[&str], u32); 7] = [
            (
                &[
                    "john", "wei", "wang", "wu", "li", "lin", "dai", "chen", "zhang", "yang",
                ],
                2_000_000,
            ),
            (
                &["smith", "maria", "kevin", "von", "king", "ben", "stephen"],
                400_000,
            ),
            (&["christian", "christina", "philip", "phillip"], 1 << 17),
            (&["watanabe", "kenji", "ranasinghe", "benjamin"], 40_000),
            (&["kanishka"], 1 << 12),
            (&["korff"], 300),
            (&["kaniska"], 1 << 7),
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

    fn rec(id: BigId, name: &str, works: u32) -> Rec {
        Rec {
            orcid: "0000-0001-0000-0001".into(),
            id,
            name: Name::parse(name),
            display: name.into(),
            works,
        }
    }

    fn registered(names: &[&str]) -> Registered {
        Registered {
            names: names.iter().map(|n| Name::parse(n)).collect(),
            display: names[0].into(),
        }
    }

    fn names_given(group: &[Rec], reg: Option<&Registered>) -> Vec<(BigId, String, Reason)> {
        decide(group, reg, &freq(), &mut DerivedManifest::default())
            .into_iter()
            .filter_map(|d| match d {
                Decision::Name { keep, name, reason } => Some((keep, name, reason)),
                _ => None,
            })
            .collect()
    }

    #[test]
    fn other_scripts_transliterate() {
        assert!(same("Олександр Войтко", "Oleksandr Voitko"));
        assert!(same("Γιώργος Παπαδόπουλος", "Giorgos Papadopoulos"));
        assert!(same("王伟", "Wei Wang"));
        assert!(same("鹏 孙", "Peng Sun"));
    }

    #[test]
    fn nicknames_and_rare_one_edit_typos_match_below_an_exact_token() {
        assert!(same("Andy Spakowitz", "Andrew J. Spakowitz"));
        assert!(same("Kees van Laarhoven", "Cees van Laarhoven"));
        assert!(same("Dave Smith", "David Smith"));
        assert!(same("Liam Cunningham", "William Cunningham"));
        assert!(same("Tinging Wu", "Tingting Wu"));
        assert!(same("Kaniska Ranasinghe", "Kanishka Ranasinghe"));
        assert!(!same("Christian Smith", "Christina Smith"), "two names");
        assert!(
            same("Phillip Smith", "Philip Smith"),
            "one name in two spellings"
        );
        assert!(same("Mohamed Kowalczyk", "Muhammad Kowalczyk"));
        assert!(!same("Kevin Smith", "Kelvin Smith"), "under six letters");
        let f = freq();
        let aff = |a: &str, b: &str| affinity(&Name::parse(a), &Name::parse(b), &f);
        assert!(aff("Andrew X. Smith", "Andy Smith") < aff("Andrew X. Smith", "Andrew Smith"));
        assert!(aff("Tingting X. Wu", "Tinging Wu") < aff("Tingting X. Wu", "Tingting Wu"));
        assert!(NICKNAMES.windows(2).all(|w| w[0] < w[1]));
        assert!(NICKNAMES.iter().all(|&(n, f)| fold(n) == n && fold(f) == f));
    }

    #[test]
    fn a_capital_block_reads_as_initials_or_as_a_name() {
        assert!(same("Wei LI", "Wei Li"));
        assert!(same("LI Wei", "Wei Li"));
        assert!(same("JK Rowling", "J. K. Rowling"));
        assert!(same("SP Hunger", "Stephen P. Hunger"));
        assert!(!same("Wei LI", "Wei Lin"));
        // Read beside its owner, "ROY SMITH" is Roy, so it does not take in a Ruth.
        let group = [rec(1, "Roy Smith", 50), rec(2, "Ruth Smith", 5)];
        let decisions = decide(
            &group,
            Some(&registered(&["ROY SMITH"])),
            &freq(),
            &mut DerivedManifest::default(),
        );
        assert_eq!(
            decisions,
            vec![Decision::Strip {
                id: 2,
                reason: Reason::NameMismatch
            }]
        );
    }

    #[test]
    fn a_merged_keep_takes_the_fullest_name() {
        let group = || vec![rec(1, "F. Halzen", 10), rec(2, "Francis Halzen", 20)];
        let halzen = |name: &str, reason| vec![(1, name.to_string(), reason)];
        assert_eq!(
            names_given(&group(), Some(&registered(&["Francis L. Halzen"]))),
            halzen("Francis L. Halzen", Reason::RegisteredName)
        );
        assert_eq!(
            names_given(&group(), None),
            halzen("Francis Halzen", Reason::LargestRecord)
        );
        for unusable in [
            "FRANCIS HALZEN",
            "francis halzen",
            "Халзен",
            "Halzen",
            "Ann Other",
        ] {
            assert_eq!(
                names_given(&group(), Some(&registered(&[unusable, "Francis Halzen"]))),
                halzen("Francis Halzen", Reason::LargestRecord),
                "{unusable}"
            );
        }
        let fuller_keep = vec![rec(1, "Francis Halzen", 10), rec(2, "F. Halzen", 20)];
        assert!(names_given(&fuller_keep, None).is_empty());
        assert!(names_given(&[rec(1, "F. Halzen", 10)], None).is_empty());
        let initialed = vec![
            rec(1, "William H. Lipscomb", 10),
            rec(2, "William Lipscomb", 20),
        ];
        assert!(names_given(&initialed, Some(&registered(&["William Lipscomb"]))).is_empty());
        let accented = vec![rec(1, "Peter Pálenský", 10), rec(2, "Peter Palensky", 20)];
        assert!(names_given(&accented, None).is_empty());
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
        assert!(ok("X. H. Wu", "Xiao-Hua Wu"));
        assert!(ok("X. L. Ji", "Xiao-Lu Ji"));
        assert!(ok("S. Paredes", "Sandra R. Paredes Saenz"));
        assert!(ok("Split", "Sam Split"));
        assert!(ok("J. J. Chen", "Jing Chen"));
        assert!(!ok("Jerome H. Siegel", "Jared Siegel"));
        assert!(!ok("Ann Other", "Sam Split"));
        assert!(!ok("Zhiliang Huang", "Pu Hu"));
        assert!(!ok("R. Zhang", "Bo Zhang"));
        assert!(!ok("D. W. Young", "David R. Young"));
        assert!(!same("X. Wu", "X. H. Wu"), "the names alone stay apart");
        assert!(ok("L. L. Ma", "Lian-Liang MA"));
    }

    #[test]
    fn spellings_of_one_name_match_and_short_common_ones_do_not() {
        assert!(same("Tieying Dai", "Tie-ying Dai"));
        assert!(same("Chen Xiang-Lei", "Xianglei Chen"));
        assert!(same("SP Hunger", "Stephen P. Hunger"));
        assert!(same("Ben King", "Benjamin King"));
        assert!(same("Mohammadmahdi Asgari", "Mohammad Mahdi Asgari"));
        assert!(!same("Li Wang", "Lin Wang"));
    }

    #[test]
    fn owner_by_registered_name_else_most_works() {
        let f = freq();
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
                Decision::Name { .. } => panic!("the keep has the fullest name"),
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
        // "Li" alone contradicts neither record but picks no owner, so the most works do;
        // the compatible cluster is then not the owner's and keeps out.
        let group = vec![rec(10, "Jun Li", 5), rec(11, "Ann Other", 50)];
        let mut manifest = DerivedManifest::default();
        let decisions = decide(&group, Some(&registered(&["Li"])), &f, &mut manifest);
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
    fn a_registered_name_of_one_full_token_vouches_for_no_cluster() {
        let f = freq();
        let group = vec![
            rec(1, "Xuemei Wu", 198),
            rec(2, "Xingyu Wu", 126),
            rec(3, "Xingyu Wu", 68),
            rec(4, "Xingyu Wu", 6),
        ];
        // No name of two full tokens names the owner, so "Sam X. Wu" does not vouch; once
        // "Xingyu Wu" does, "X WU" still does not.
        for names in [["Sam X. Wu", "X WU"], ["Xingyu Wu", "X WU"]] {
            assert_eq!(
                decide(
                    &group,
                    Some(&registered(&names)),
                    &f,
                    &mut DerivedManifest::default()
                ),
                vec![
                    Decision::Strip {
                        id: 1,
                        reason: Reason::NameMismatch
                    },
                    Decision::Merge {
                        drop: 3,
                        keep: 2,
                        reason: Reason::RegisteredName
                    },
                    Decision::Merge {
                        drop: 4,
                        keep: 2,
                        reason: Reason::RegisteredName
                    },
                ],
                "{names:?}"
            );
        }
    }

    #[test]
    fn a_full_registered_name_vouches_beside_an_initialed_owner() {
        let group = vec![
            rec(1, "H. J. Yang", 50),
            rec(2, "H. J. Yang", 30),
            rec(3, "Haijun Yang", 20),
        ];
        let registered = registered(&["H.J. Yang", "Hai-Jun Yang", "Haijun Yang"]);
        assert_eq!(
            decide(
                &group,
                Some(&registered),
                &freq(),
                &mut DerivedManifest::default()
            ),
            vec![
                Decision::Merge {
                    drop: 2,
                    keep: 1,
                    reason: Reason::RegisteredName
                },
                Decision::Merge {
                    drop: 3,
                    keep: 1,
                    reason: Reason::CompatibleName
                },
            ]
        );
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
