mod fixed_heap;
mod io;
mod merging;
#[cfg(test)]
mod tests;

use deunicode::deunicode;
pub use fixed_heap::{FixedHeap, Maxed, Mined};
use merging::logfound;
pub use merging::{
    log_search, ordered_calls, sorted_iters_to_arr, ArrExtender, ExtendableArr, OrderedMapper,
};

use std::cmp::Reverse;
use std::convert::TryInto;
use std::fmt::Debug;
use std::ops::AddAssign;

type IndType = u32;

const SPLIT_CHAR: u8 = 32;
const ASCII_LC_MIN: u8 = 97;
const ASCII_LC_MAX: u8 = 122;
const ASCII_COUNT: usize = 26;
const CHAR_COUNT: usize = ASCII_COUNT;

const MAX_QUERY_CHARS: usize = 256;
const MAX_QUERY_WORDS: usize = 32;
const MAX_MATCHED_WORDS: usize = 3;

const BRANCHING_LEVELS: usize = 2;

type IndOutTrie<NL, const S: usize> = GenTrie<NL, FixedHeap<IndType, S>>;
type TrieNodeRoot<const S: usize> = IndOutTrie<TrieNodeL1<S>, S>;
type TrieNodeL1<const S: usize> = IndOutTrie<TrieLeaves, S>;

type PrepTrieL1<const S: usize> = IndOutTrie<Vec<PrepLeaf>, S>;
type PrepTrieRoot<const S: usize> = IndOutTrie<PrepTrieL1<S>, S>;

pub struct SearchEngine<const S: usize> {
    tree: CustomTrie<S>,
}

struct QueryResult {
    perfect: Vec<IndType>,
    partial: Vec<IndType>,
}

#[derive(Debug, Clone, PartialEq)]
struct WordViaCharr {
    start_idx: u32,
    len: u16,
}

pub struct StackWordSet {
    char_array: [u8; MAX_QUERY_CHARS],
    break_array: [u8; MAX_QUERY_WORDS],
    breaks_count: usize,
}

struct GenTrie<NextLevel, Out> {
    children: [NextLevel; CHAR_COUNT],
    out: Out,
}

struct CustomTrie<const S: usize> {
    prefix_tree: TrieNodeRoot<S>,
    inner_tree: TrieNodeRoot<S>,
    // per letter, the ids of the haystacks with a word starting with it
    by_initial: [Box<[IndType]>; CHAR_COUNT],
    char_array: Box<[u8]>,
}

#[derive(Debug)]
struct TrieLeaves(Box<[TrieLeaf]>);

#[derive(Debug)]
struct TrieLeaf {
    suffix: WordViaCharr,
    ids: Box<[IndType]>,
}

struct PrepLeaf {
    suffix: WordViaCharr,
    ids: Vec<IndType>,
}

struct IndexedWord {
    word: Vec<u8>,
    outer_idx: usize,
}

trait Construct {
    fn new() -> Self;
}

trait QueriableLevel {
    fn query(&self, word: &[u8], char_arr: &[u8], include: Option<&[IndType]>) -> QueryResult;
    fn query_inners(
        &self,
        word: &[u8],
        char_arr: &[u8],
        include: Option<&[IndType]>,
    ) -> Vec<IndType>;
}

impl<T, const S: usize> IndOutTrie<T, S> {
    fn rel_inds(&self, include: Option<&[IndType]>) -> Vec<IndType> {
        self.out
            .arr
            .into_iter()
            .take_while(|e| *e < IndType::MAX)
            .filter(|e| included(include, *e))
            .collect()
    }
}

impl TrieLeaves {
    // leaves are sorted by suffix, so the ones extending `rest` form one run, led by its equal
    fn range(&self, char_arr: &[u8], rest: &[u8]) -> &[TrieLeaf] {
        let start = self.0.partition_point(|e| e.suffix.cut(char_arr) < rest);
        let len = self.0[start..].partition_point(|e| e.suffix.cut(char_arr).starts_with(rest));
        &self.0[start..start + len]
    }
}

impl From<QueryResult> for Vec<IndType> {
    fn from(mut val: QueryResult) -> Self {
        extend_sorted(&mut val.perfect, val.partial);
        val.perfect
    }
}

impl<T> Construct for Vec<T> {
    fn new() -> Self {
        Self::new()
    }
}

impl<T: Iterator<Item = TrieLeaf>> From<T> for TrieLeaves {
    fn from(value: T) -> Self {
        Self(value.collect::<Vec<TrieLeaf>>().try_into().unwrap())
    }
}

impl<T: Construct, const S: usize> Construct for IndOutTrie<T, S> {
    fn new() -> Self {
        let children = core::array::from_fn(|_| T::new());
        Self {
            children,
            out: FixedHeap::new(),
        }
    }
}

impl<T: QueriableLevel, const S: usize> QueriableLevel for IndOutTrie<T, S> {
    fn query(&self, word: &[u8], char_arr: &[u8], include: Option<&[IndType]>) -> QueryResult {
        match word.split_first() {
            None => QueryResult {
                perfect: self.rel_inds(include),
                partial: Vec::new(),
            },
            Some((c, rest)) => self.children[*c as usize].query(rest, char_arr, include),
        }
    }

    fn query_inners(
        &self,
        word: &[u8],
        char_arr: &[u8],
        include: Option<&[IndType]>,
    ) -> Vec<IndType> {
        match word.split_first() {
            None => self.rel_inds(include),
            Some((c, rest)) => self.children[*c as usize].query_inners(rest, char_arr, include),
        }
    }
}

impl QueriableLevel for TrieLeaves {
    fn query(&self, word: &[u8], char_arr: &[u8], include: Option<&[IndType]>) -> QueryResult {
        let range = self.range(char_arr, word);
        let (equal, longer) =
            range.split_at(range.partition_point(|e| e.suffix.len as usize == word.len()));
        QueryResult {
            perfect: collect_ids(equal, include),
            partial: collect_ids(longer, include),
        }
    }

    fn query_inners(
        &self,
        word: &[u8],
        char_arr: &[u8],
        include: Option<&[IndType]>,
    ) -> Vec<IndType> {
        collect_ids(self.range(char_arr, word), include)
    }
}

impl<const S: usize> PrepTrieRoot<S> {
    fn finalize(mut self, char_array: &[u8]) -> TrieNodeRoot<S> {
        self.out.sort();
        let out = self.out;
        let children = child_into(self.children, |c| c.finalize(char_array));
        TrieNodeRoot { out, children }
    }

    fn extend(
        &mut self,
        idxed_word: &IndexedWord,
        char_array: &mut Vec<u8>,
        start_char: usize,
        last_suff: &[u8],
    ) -> Vec<u8> {
        let full_word = &idxed_word.word[start_char..];
        self.out.push_unique(idxed_word.outer_idx as IndType);
        if full_word.len() < 1 {
            return last_suff.into();
        }
        let l1 = &mut self.children[full_word[0] as usize];
        l1.out.push_unique(idxed_word.outer_idx as IndType);
        if full_word.len() < 2 {
            return last_suff.into();
        }
        let l2 = &mut l1.children[full_word[1] as usize];
        let suffix = &full_word[BRANCHING_LEVELS..];
        let overlap = get_overlap(suffix, last_suff);
        char_array.extend(suffix[overlap..].iter());
        let ln = suffix.len();
        let suff_by_idx = WordViaCharr {
            start_idx: (char_array.len() - ln) as u32,
            len: ln as u16,
        };
        let l2_idx = get_i(l2, suff_by_idx);
        let oind = idxed_word.outer_idx as IndType;
        if !l2[l2_idx].ids.contains(&oind) {
            l2[l2_idx].ids.push(idxed_word.outer_idx as IndType);
        }
        suffix.into()
    }
}

impl<const S: usize> PrepTrieL1<S> {
    fn finalize(mut self, char_array: &[u8]) -> TrieNodeL1<S> {
        self.out.sort();
        let out = self.out;
        let children = child_into(self.children, |mut c| {
            c.sort_by_key(|tl| tl.suffix.cut(char_array));
            c.into_iter()
                .map(|mut leaf| {
                    leaf.ids.sort();
                    TrieLeaf {
                        ids: leaf.ids.into(),
                        suffix: leaf.suffix,
                    }
                })
                .into()
        });
        TrieNodeL1 { out, children }
    }
}

impl WordViaCharr {
    fn cut<'a>(&self, char_arr: &'a [u8]) -> &'a [u8] {
        let su = self.start_idx as usize;
        &char_arr[su..(su + self.len as usize)]
    }
}

impl<const S: usize> CustomTrie<S> {
    fn new(mut idxed_words: Vec<IndexedWord>) -> Self {
        idxed_words.sort_by(|l, r| get_suffix(&l.word).cmp(&get_suffix(&r.word)));
        let mut char_array = Vec::new();
        let mut last_suff: Vec<u8> = Vec::new();
        let mut prep_tree = PrepTrieRoot::new();
        let mut inner_prep = PrepTrieRoot::new();
        let mut by_initial: [Vec<IndType>; CHAR_COUNT] = core::array::from_fn(|_| Vec::new());

        for idxed_word in idxed_words.into_iter().rev().filter(|e| e.word.len() > 0) {
            by_initial[idxed_word.word[0] as usize].push(idxed_word.outer_idx as IndType);
            last_suff = prep_tree.extend(&idxed_word, &mut char_array, 0, &last_suff);
            for i in 1..(idxed_word.word.len() - 1) {
                inner_prep.extend(&idxed_word, &mut char_array, i, &last_suff);
            }
        }
        Self {
            prefix_tree: prep_tree.finalize(&char_array),
            inner_tree: inner_prep.finalize(&char_array),
            by_initial: child_into(by_initial, |mut ids| {
                ids.sort_unstable();
                ids.dedup();
                ids.into()
            }),
            char_array: char_array.into(),
        }
    }

    // The longest word is matched first, as the most selective, and the rest narrow it down;
    // `perfect` keeps the ids matching every word whole.
    fn query(&self, sword: &StackWordSet, limit: usize) -> Vec<IndType> {
        let mut words = sword.words();
        words.sort_by_key(|w| Reverse(w.len()));
        let first = words.first().copied().unwrap_or_default();
        let mut matches = self.prefix_tree.query(first, &self.char_array, None);
        if words.len() > 1 || matches.perfect.len() + matches.partial.len() < limit {
            let inner = self.inner_tree.query_inners(first, &self.char_array, None);
            matches.partial = union(&matches.partial, &inner);
        }
        words
            .iter()
            .skip(1)
            .take(MAX_MATCHED_WORDS - 1)
            .fold(matches, |matches, word| self.narrow(matches, word))
            .into()
    }

    fn narrow(&self, matches: QueryResult, word: &[u8]) -> QueryResult {
        let include = union(&matches.perfect, &matches.partial);
        // a lone letter matches whole as an initial, whether bare or starting a word
        let found = match word {
            [c] => QueryResult {
                perfect: intersect(&include, &self.by_initial[*c as usize]),
                partial: Vec::new(),
            },
            _ => {
                let mut found = self
                    .prefix_tree
                    .query(word, &self.char_array, Some(&include));
                let inner = self
                    .inner_tree
                    .query_inners(word, &self.char_array, Some(&include));
                found.partial = union(&found.partial, &inner);
                found
            }
        };
        QueryResult {
            perfect: intersect(&found.perfect, &matches.perfect),
            partial: union(&found.perfect, &found.partial),
        }
    }
}

impl StackWordSet {
    pub fn new(words: &str) -> Self {
        let mut out = Self {
            char_array: [0; MAX_QUERY_CHARS],
            break_array: [0; MAX_QUERY_WORDS],
            breaks_count: 0,
        };
        let mut i: u8 = 0;
        for c in deunicode(words).bytes().map(|b| b.to_ascii_lowercase()) {
            if (c == SPLIT_CHAR) && (i > 0) {
                out.new_break(i);
                if out.breaks_count == MAX_QUERY_WORDS {
                    return out;
                }
            } else if (c >= ASCII_LC_MIN) && (c <= ASCII_LC_MAX) {
                out.char_array[i as usize] = c - ASCII_LC_MIN;
                i = i.wrapping_add(1);
                if i == 0 {
                    return out;
                }
            }
        }
        out.new_break(i);
        out
    }

    pub fn to_words(&self) -> Vec<String> {
        self.words()
            .into_iter()
            .map(|w| {
                String::from_utf8(w.iter().map(|c| c + ASCII_LC_MIN).collect())
                    .expect("reading word")
            })
            .collect()
    }

    fn words(&self) -> Vec<&[u8]> {
        let mut start = 0;
        self.break_array[..self.breaks_count]
            .iter()
            .map(|&end| {
                let word = &self.char_array[start..end as usize];
                start = end as usize;
                word
            })
            .collect()
    }

    fn new_break(&mut self, i: u8) {
        let last_break = if self.breaks_count > 0 {
            self.break_array[self.breaks_count - 1]
        } else {
            0
        };
        if last_break != i {
            self.break_array[self.breaks_count as usize] = i as u8;
            self.breaks_count.add_assign(1);
        }
    }
}

impl<const S: usize> SearchEngine<S> {
    pub fn new<I: Iterator<Item = String>>(haystacks: I) -> Self {
        let idxed_words = get_idxed_words(haystacks);
        let trie = CustomTrie::new(idxed_words);
        Self { tree: trie.into() }
    }

    pub fn query(&self, query: &str) -> Vec<IndType> {
        let sword = StackWordSet::new(query);
        self.tree.query(&sword, S).into_iter().take(S).collect()
    }
}

//adds elems that are not present
fn extend_sorted<T: PartialOrd>(int_v: &mut Vec<T>, add_v: Vec<T>) {
    let mut i = 0;
    let init_i_len = int_v.len();
    let mut last_ge = None;
    for add_e in add_v.into_iter() {
        while i < init_i_len {
            if int_v[i] < add_e {
                i += 1;
            } else {
                last_ge = Some(i);
                break;
            }
        }
        if match last_ge {
            None => true,
            Some(i) => add_e != int_v[i],
        } {
            int_v.push(add_e)
        }
    }
}

fn collect_ids<'a>(
    leaves: impl IntoIterator<Item = &'a TrieLeaf>,
    include: Option<&[IndType]>,
) -> Vec<IndType> {
    let mut ids: Vec<IndType> = leaves
        .into_iter()
        .flat_map(|leaf| leaf.ids.iter().copied())
        .filter(|&id| included(include, id))
        .collect();
    ids.sort_unstable();
    ids.dedup();
    ids
}

fn included(include: Option<&[IndType]>, id: IndType) -> bool {
    include.is_none_or(|inc| logfound(inc, id))
}

fn union(left: &[IndType], right: &[IndType]) -> Vec<IndType> {
    let mut out = Vec::with_capacity(left.len() + right.len());
    sorted_iters_to_arr(&mut out, left.iter(), right.iter());
    out
}

fn intersect(left: &[IndType], right: &[IndType]) -> Vec<IndType> {
    left.iter()
        .copied()
        .filter(|&id| logfound(right, id))
        .collect()
}

fn get_idxed_words<I: Iterator<Item = String>>(haystacks: I) -> Vec<IndexedWord> {
    let mut idxed_words = Vec::new();
    for (hi, haystack) in haystacks.enumerate() {
        let wstack = StackWordSet::new(&haystack);
        for word in wstack.words() {
            idxed_words.push(IndexedWord {
                word: word.to_vec(),
                outer_idx: hi,
            });
        }
    }
    idxed_words
}

fn get_suffix(word: &[u8]) -> &[u8] {
    word.get(BRANCHING_LEVELS..).unwrap_or_default()
}

fn get_overlap<T: PartialEq>(suffix: &[T], word: &[T]) -> usize {
    if word.ends_with(suffix) {
        suffix.len()
    } else {
        0
    }
}

fn get_i(v: &mut Vec<PrepLeaf>, e: WordViaCharr) -> usize {
    // suffix-sorted insertion makes equal suffixes consecutive, so the match is almost
    // always the last leaf; the scan below only runs for unsorted inner-tree calls
    if let Some(pl) = v.last() {
        if e == pl.suffix {
            return v.len() - 1;
        }
    }
    for (i, pl) in v.iter().enumerate() {
        if e == pl.suffix {
            return i;
        }
    }
    v.push(PrepLeaf {
        suffix: e,
        ids: Vec::new(),
    });
    return v.len() - 1;
}

fn child_into<S, T, F>(children: [S; CHAR_COUNT], f: F) -> [T; CHAR_COUNT]
where
    F: FnMut(S) -> T,
{
    match children.into_iter().map(f).collect::<Vec<T>>().try_into() {
        Ok(a) => a,
        Err(_) => panic!("cant collect to {CHAR_COUNT}"),
    }
}
