//! What publishers' DOIs say about work records: a record that is no paper, or two records that
//! are one. The two tables here are the only place a journal or service is named; the work screen
//! (`WORK_SCREEN.abstract_doi_prefixes`) and the derived paper merges (`edition_merges`, written
//! by `derive-ledger`) read them and know nothing of any publisher.

use dmove::BigId;
use hashbrown::{HashMap, HashSet};

use crate::{
    common::{oa_id_parse_opt, ParsedId, Stowage, MAIN_NAME},
    csv_iter::par_reduce,
    csv_writers::works,
    oa_structs::{post::Authorship, Work},
    user_ledger::strip_doi_prefix,
};

/// DOI prefixes of the records an abstracting service files under the abstracted paper's authors.
pub const ABSTRACT_COPY_PREFIXES: &[&str] = &[
    // ChemInform and its predecessor, Chemischer Informationsdienst
    "10.1002/chin.",
];

/// Journals published in two editions, a paper under one number after both prefixes.
pub const EDITION_PAIRS: &[EditionPair] = &[
    // Angewandte Chemie in German and as the International Edition, the German one alone before
    // 1962. Each edition numbered its own articles until 2003, and covers still are numbered
    // apart: the shared author tells the twins.
    EditionPair {
        copy: "10.1002/ange.",
        original: "10.1002/anie.",
    },
];

/// A paper's edition key: its pair in `EDITION_PAIRS` and the number after the prefix.
type EditionKey = (usize, String);

/// The `copy` edition's record of a paper merges into the `original` edition's.
pub struct EditionPair {
    pub copy: &'static str,
    pub original: &'static str,
}

/// (drop, keep): each copy-edition record into the lowest-id original-edition record of its key
/// that shares an author with it. A number alone is not a paper, and a copy without such a twin
/// stays.
pub fn edition_merges(stowage: &Stowage) -> Vec<(BigId, BigId)> {
    let twins = twinned(par_reduce::<Work, Vec<(EditionKey, BigId, bool)>, _, _>(
        stowage,
        works::C,
        MAIN_NAME,
        |acc, w| {
            if let (Some(id), Some((key, original))) =
                (w.get_parsed_id(), w.doi.as_deref().and_then(edition))
            {
                acc.push((key, id, original));
            }
        },
        |a, b| a.extend(b),
        Some(10),
    ));
    let wanted: std::sync::Arc<HashSet<BigId>> = std::sync::Arc::new(
        twins
            .iter()
            .flat_map(|(copies, originals)| copies.iter().chain(originals))
            .copied()
            .collect(),
    );
    let authors = par_reduce::<Authorship, HashMap<BigId, Vec<BigId>>, _, _>(
        stowage,
        works::C,
        works::atts::authorships,
        move |acc, s| {
            let work = s.parent_id.as_deref().and_then(oa_id_parse_opt);
            let author = s.author_id.as_deref().and_then(oa_id_parse_opt);
            if let (Some(w), Some(a)) = (work.filter(|w| wanted.contains(w)), author) {
                acc.entry(w).or_default().push(a);
            }
        },
        |a, b| {
            for (w, authors) in b {
                a.entry(w).or_default().extend(authors);
            }
        },
        Some(10),
    );
    pair_editions(&twins, &authors)
}

/// A record's edition key and whether it is the original edition's.
fn edition(doi: &str) -> Option<(EditionKey, bool)> {
    let doi = strip_doi_prefix(doi);
    EDITION_PAIRS.iter().enumerate().find_map(|(pair, p)| {
        [(p.copy, false), (p.original, true)]
            .into_iter()
            .find_map(|(prefix, original)| {
                let number = doi.get(prefix.len()..)?;
                doi[..prefix.len()]
                    .eq_ignore_ascii_case(prefix)
                    .then(|| ((pair, number.to_ascii_lowercase()), original))
            })
    })
}

/// (copy records, original records by id) of each key both editions carry.
fn twinned(editions: Vec<(EditionKey, BigId, bool)>) -> Vec<(Vec<BigId>, Vec<BigId>)> {
    let mut by_key: HashMap<EditionKey, (Vec<BigId>, Vec<BigId>)> = HashMap::new();
    for (key, id, original) in editions {
        let (copies, originals) = by_key.entry(key).or_default();
        if original { originals } else { copies }.push(id);
    }
    by_key
        .into_values()
        .filter(|(copies, originals)| !(copies.is_empty() || originals.is_empty()))
        .map(|(copies, mut originals)| {
            originals.sort_unstable();
            (copies, originals)
        })
        .collect()
}

fn pair_editions(
    twins: &[(Vec<BigId>, Vec<BigId>)],
    authors: &HashMap<BigId, Vec<BigId>>,
) -> Vec<(BigId, BigId)> {
    let none = Vec::new();
    let of = |w: &BigId| authors.get(w).unwrap_or(&none);
    let mut pairs: Vec<(BigId, BigId)> = twins
        .iter()
        .flat_map(|(copies, originals)| {
            copies.iter().filter_map(|c| {
                originals
                    .iter()
                    .find(|o| of(c).iter().any(|a| of(o).contains(a)))
                    .map(|&o| (*c, o))
            })
        })
        .collect();
    pairs.sort_unstable();
    pairs
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_copy_edition_record_folds_into_its_twin_that_shares_an_author() {
        let record = |doi: &str, id: BigId| {
            let (key, original) = edition(doi).unwrap();
            (key, id, original)
        };
        let [pair] = EDITION_PAIRS else {
            panic!("the test reads one pair")
        };
        let doi = |prefix: &str, number: &str| format!("https://doi.org/{prefix}{number}");
        assert_eq!(edition("https://doi.org/10.1021/ja00528a029"), None);
        let twins = twinned(vec![
            record(&doi(pair.copy, "200705241"), 1),
            record(&doi(&pair.original.to_uppercase(), "200705241"), 3),
            record(&doi(pair.original, "200705241"), 2),
            // a number each edition gave to a different article
            record(&doi(pair.copy, "200390073"), 6),
            record(&doi(pair.original, "200390073"), 7),
            // a copy without a twin, an original without one
            record(&doi(pair.copy, "19620740102"), 4),
            record(&doi(pair.original, "201608955"), 5),
        ]);
        let authors = [
            (1, vec![10, 11]),
            (2, vec![9]),
            (3, vec![11]),
            (6, vec![12]),
            (7, vec![13]),
        ]
        .into_iter()
        .collect();
        assert_eq!(pair_editions(&twins, &authors), vec![(1, 3)]);
    }
}
