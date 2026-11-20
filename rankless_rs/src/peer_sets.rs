use std::fmt;

use dmove::BigId;
use hashbrown::{HashMap, HashSet};

use crate::common::short_oa_id_parse;

// `set,openalex_id,name`: institutions of one type per set, labelled by hand. A member's peers are
// expected among the other members. No set lists its whole type, so a precision reads against
// another run's over the same sets, not against 1.
const PEER_SETS: &str = include_str!("../static/peer-sets.csv");

pub struct PeerSet {
    pub name: &'static str,
    pub members: Vec<BigId>,
}

/// The stored peers of one set's members, counted over the members that have peers.
pub struct SetScore {
    pub name: &'static str,
    pub labelled: usize,
    pub scored: usize,
    pub hits: usize,
    /// The slots a ranking could fill with members: each scored member's, up to the other scored
    /// members.
    pub fillable: usize,
    pub same_group: usize,
    pub peers: usize,
}

/// The per-set rows and their total as a markdown table; `N` is the number of peer slots.
pub struct ScoreTable<'a, const N: usize>(pub &'a [SetScore]);

impl SetScore {
    /// Share of the scored members' `N` peer slots that hold another scored member of the set.
    pub fn precision<const N: usize>(&self) -> f64 {
        ratio(self.hits, self.scored * N)
    }

    /// The precision of a ranking that fills every slot it can with members.
    pub fn ceiling<const N: usize>(&self) -> f64 {
        ratio(self.fillable, self.scored * N)
    }

    /// Share of the scored members' peers in the member's own group.
    pub fn same_group_share(&self) -> f64 {
        ratio(self.same_group, self.peers)
    }

    fn total(scores: &[Self]) -> Self {
        let sum = |f: fn(&Self) -> usize| -> usize { scores.iter().map(f).sum() };
        Self {
            name: "all",
            labelled: sum(|s| s.labelled),
            scored: sum(|s| s.scored),
            hits: sum(|s| s.hits),
            fillable: sum(|s| s.fillable),
            same_group: sum(|s| s.same_group),
            peers: sum(|s| s.peers),
        }
    }

    fn row<const N: usize>(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(
            f,
            "| {} | {}/{} | {:.3} | {:.2} | {:.2} |",
            self.name,
            self.scored,
            self.labelled,
            self.precision::<N>(),
            self.ceiling::<N>(),
            self.same_group_share(),
        )
    }
}

impl<const N: usize> fmt::Display for ScoreTable<'_, N> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(
            f,
            "| set | scored/labelled | P@{N} | ceiling | same country |"
        )?;
        writeln!(f, "| --- | --: | --: | --: | --: |")?;
        for score in self.0 {
            score.row::<N>(f)?;
        }
        SetScore::total(self.0).row::<N>(f)
    }
}

pub fn labelled_sets() -> Vec<PeerSet> {
    let mut sets: Vec<PeerSet> = Vec::new();
    for line in PEER_SETS.lines().skip(1) {
        let mut fields = line.splitn(3, ',');
        let (Some(set), Some(oa_id)) = (fields.next(), fields.next()) else {
            panic!("malformed peer set line: {line}");
        };
        let oa_id = short_oa_id_parse(oa_id);
        match sets.last_mut() {
            Some(last) if last.name == set => last.members.push(oa_id),
            _ => sets.push(PeerSet {
                name: set,
                members: vec![oa_id],
            }),
        }
    }
    sets
}

/// `ids` maps an OpenAlex id to its row in `peers` and `groups`. A peer slot holding 0 is empty,
/// group 0 is no group, and only the members the root gives peers are scored, as members and as
/// hits, so a precision never passes its ceiling.
pub fn score_sets<const N: usize>(
    sets: &[PeerSet],
    ids: &HashMap<BigId, usize>,
    peers: &[[usize; N]],
    groups: &[usize],
) -> Vec<SetScore> {
    let found = |row: usize| peers[row].iter().copied().filter(|&p| p != 0);
    sets.iter()
        .map(|set| {
            let scored: HashSet<usize> = member_rows(set, ids)
                .into_iter()
                .filter(|&row| found(row).next().is_some())
                .collect();
            let (mut hits, mut same_group, mut n_peers) = (0, 0, 0);
            for &row in &scored {
                for peer in found(row) {
                    n_peers += 1;
                    hits += scored.contains(&peer) as usize;
                    same_group += (groups[row] != 0 && groups[peer] == groups[row]) as usize;
                }
            }
            SetScore {
                name: set.name,
                labelled: set.members.len(),
                scored: scored.len(),
                hits,
                fillable: scored.len() * scored.len().saturating_sub(1).min(N),
                same_group,
                peers: n_peers,
            }
        })
        .collect()
}

/// The rows of the set's members the root holds.
pub fn member_rows(set: &PeerSet, ids: &HashMap<BigId, usize>) -> HashSet<usize> {
    set.members
        .iter()
        .filter_map(|m| ids.get(m).copied())
        .collect()
}

fn ratio(part: usize, whole: usize) -> f64 {
    if whole == 0 {
        0.0
    } else {
        part as f64 / whole as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn labelled_sets_hold_each_institution_once() {
        let sets = labelled_sets();
        let names: HashSet<&str> = sets.iter().map(|s| s.name).collect();
        assert_eq!(names.len(), sets.len(), "a set's rows are not contiguous");
        let members: Vec<BigId> = sets
            .iter()
            .flat_map(|s| s.members.iter().copied())
            .collect();
        let unique: HashSet<BigId> = members.iter().copied().collect();
        assert_eq!(
            unique.len(),
            members.len(),
            "an institution is labelled twice"
        );
        assert!(sets.iter().all(|s| s.members.len() > 2));
    }

    #[test]
    fn scores_count_members_among_stored_peers() {
        let sets = [
            PeerSet {
                name: "a",
                members: vec![10, 20, 30, 99],
            },
            PeerSet {
                name: "b",
                members: vec![40, 50],
            },
        ];
        let ids: HashMap<BigId, usize> = [(10, 1), (20, 2), (30, 3), (40, 4), (50, 5)].into();
        // Row 0 is the padding entity; 3 has no peers, so it is no hit as a peer of 2; 4 and 5 are
        // peers of nobody in their set.
        let peers: [[usize; 2]; 6] = [[0, 0], [2, 4], [1, 3], [0, 0], [1, 0], [2, 1]];
        let groups = [0, 7, 7, 7, 0, 8];
        let scores = score_sets(&sets, &ids, &peers, &groups);

        let a = &scores[0];
        assert_eq!((a.labelled, a.scored, a.hits, a.peers), (4, 2, 2, 4));
        assert_eq!(a.same_group, 3);
        assert_eq!(a.precision::<2>(), 0.5);
        assert_eq!(a.ceiling::<2>(), 0.5);

        let b = &scores[1];
        assert_eq!((b.scored, b.hits, b.peers, b.same_group), (2, 0, 3, 0));
        assert_eq!(b.precision::<2>(), 0.0);
        assert!(scores
            .iter()
            .all(|s| s.precision::<2>() <= s.ceiling::<2>()));

        let table = ScoreTable::<2>(&scores).to_string();
        assert!(table.contains("| a | 2/4 | 0.500 | 0.50 | 0.75 |"));
        assert!(table.ends_with("| all | 4/6 | 0.250 | 0.50 | 0.43 |\n"));
    }
}
