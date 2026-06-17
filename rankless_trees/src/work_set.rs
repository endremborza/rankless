use crate::io::WT;

// Intersection of work-id sets expressed in conjunctive normal form: an AND of
// OR-clauses. Each clause is a list of operand slices (the OR), clauses are
// intersected (the AND). Every operand slice MUST be sorted ascending and
// de-duplicated; the `MainWorkMarker` lists satisfy this by construction —
// `derive_links1::invert_links_sorted` fills each bucket with the outer loop's
// `enumerate` index, which only increases, so every inverted list is
// monotonic. The `debug_assert!` in `cnf_intersect` documents and dev-checks
// the precondition for this general-purpose function.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TooBroad {
    pub min_clause_bound: usize,
    pub max_base: usize,
}

/// Sorted intersection of a CNF of sorted operand slices.
///
/// Work is bounded by the smallest clause: its union (≤ `max_base`) is
/// materialised, then every candidate is kept only if every other clause
/// contains it (a clause contains a wid iff any of its operands does). Returns
/// `Err(TooBroad)` when even the smallest clause's union upper bound exceeds
/// `max_base`, so the caller can reject an unbounded query instead of grinding
/// through millions of membership tests.
pub fn cnf_intersect(clauses: &[Vec<&[WT]>], max_base: usize) -> Result<Vec<WT>, TooBroad> {
    if clauses.is_empty() {
        return Ok(Vec::new());
    }
    debug_assert!(
        clauses
            .iter()
            .flatten()
            .all(|s| s.windows(2).all(|w| w[0] < w[1])),
        "cnf_intersect operands must be sorted ascending and de-duplicated"
    );

    let bound = |c: &Vec<&[WT]>| c.iter().map(|s| s.len()).sum::<usize>();
    let (base_idx, min_bound) = clauses
        .iter()
        .enumerate()
        .map(|(i, c)| (i, bound(c)))
        .min_by_key(|(_, b)| *b)
        .unwrap();

    // An OR-clause with no work content makes the whole AND empty.
    if min_bound == 0 {
        return Ok(Vec::new());
    }
    if min_bound > max_base {
        return Err(TooBroad {
            min_clause_bound: min_bound,
            max_base,
        });
    }

    let candidates = union_sorted(&clauses[base_idx]);
    Ok(candidates
        .into_iter()
        .filter(|&wid| {
            clauses
                .iter()
                .enumerate()
                .all(|(i, clause)| i == base_idx || clause_contains(clause, wid))
        })
        .collect())
}

fn clause_contains(clause: &[&[WT]], wid: WT) -> bool {
    clause.iter().any(|s| s.binary_search(&wid).is_ok())
}

// k-way union of sorted slices → sorted, de-duplicated. Operand counts are
// small (capped by the handler), and the base clause is ≤ `max_base`, so a
// concat-sort-dedup is both simple and fast enough; a single operand is the hot
// path (e.g. the two-way author intersection) and skips the sort entirely.
fn union_sorted(operands: &[&[WT]]) -> Vec<WT> {
    match operands {
        [] => Vec::new(),
        [only] => only.to_vec(),
        _ => {
            let mut v = Vec::with_capacity(operands.iter().map(|s| s.len()).sum());
            for s in operands {
                v.extend_from_slice(s);
            }
            v.sort_unstable();
            v.dedup();
            v
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const BIG: usize = usize::MAX;

    #[test]
    fn and_of_singles() {
        let a: &[WT] = &[1, 3, 5, 7, 9];
        let b: &[WT] = &[3, 4, 5, 6, 9];
        let clauses = vec![vec![a], vec![b]];
        assert_eq!(cnf_intersect(&clauses, BIG).unwrap(), vec![3, 5, 9]);
    }

    #[test]
    fn or_within_clause() {
        // (a OR b) AND c
        let a: &[WT] = &[1, 2, 3];
        let b: &[WT] = &[8, 9];
        let c: &[WT] = &[2, 3, 8, 100];
        let clauses = vec![vec![a, b], vec![c]];
        assert_eq!(cnf_intersect(&clauses, BIG).unwrap(), vec![2, 3, 8]);
    }

    #[test]
    fn result_is_sorted_and_deduped() {
        let a: &[WT] = &[1, 2, 4, 8, 16];
        let b: &[WT] = &[2, 8];
        let c: &[WT] = &[8, 8888]; // overlapping union sources still dedup
        let clauses = vec![vec![a], vec![b, c]];
        let out = cnf_intersect(&clauses, BIG).unwrap();
        assert_eq!(out, vec![2, 8]);
        assert!(out.windows(2).all(|w| w[0] < w[1]));
    }

    #[test]
    fn empty_clause_makes_empty() {
        let a: &[WT] = &[1, 2, 3];
        let empty: Vec<&[WT]> = vec![];
        let clauses = vec![vec![a], empty];
        assert!(cnf_intersect(&clauses, BIG).unwrap().is_empty());
    }

    #[test]
    fn no_clauses_is_empty() {
        let clauses: Vec<Vec<&[WT]>> = vec![];
        assert!(cnf_intersect(&clauses, BIG).unwrap().is_empty());
    }

    #[test]
    fn too_broad_when_min_clause_exceeds_base() {
        let big_a: Vec<WT> = (0..100).collect();
        let big_b: Vec<WT> = (50..200).collect();
        let clauses = vec![vec![big_a.as_slice()], vec![big_b.as_slice()]];
        let err = cnf_intersect(&clauses, 99).unwrap_err();
        assert_eq!(err.max_base, 99);
        assert_eq!(err.min_clause_bound, 100);
    }

    #[test]
    fn base_is_smallest_clause() {
        // huge first clause, tiny second; must still be cheap + correct.
        let huge: Vec<WT> = (0..10_000).collect();
        let tiny: &[WT] = &[42, 9_999, 10_500];
        let clauses = vec![vec![huge.as_slice()], vec![tiny]];
        // base = tiny (bound 3) so max_base of 3 is enough despite the 10k clause.
        assert_eq!(cnf_intersect(&clauses, 3).unwrap(), vec![42, 9_999]);
    }
}
