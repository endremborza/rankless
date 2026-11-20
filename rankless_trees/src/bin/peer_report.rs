//! `peer-report <root> [set]`: the precision of the root's stored institution peers against the
//! hand-labelled sets (`rankless_rs::peer_sets`); with a set name, that set's members with their
//! peers, the ones inside the set marked. Writes no data.

use hashbrown::HashMap;

use dmove::{BigId, UnsignedNumber};
use rankless_rs::{
    gen::{a1_entity_mapping::Institutions, a2_init_atts::InstCountries},
    peer_sets::{labelled_sets, member_rows, score_sets, PeerSet, ScoreTable},
    NameMarker, PeerMarker, QuickestBox, QuickestNumbered, ReadIter, Stowage, N_PEERS,
};

type PeerRow = [usize; N_PEERS];

fn main() {
    let mut args = std::env::args().skip(1);
    let root = args.next().expect("usage: peer-report <root> [set]");
    let stowage = Stowage::new(&root);

    let ids: HashMap<BigId, usize> = stowage
        .get_entity_interface::<Institutions, QuickestNumbered>()
        .0
        .into_iter()
        .map(|(oa_id, id)| (oa_id, id.to_usize()))
        .collect();
    let peers: Vec<PeerRow> = stowage
        .get_marked_interface::<Institutions, PeerMarker, QuickestBox>()
        .iter()
        .map(|row| row.map(|p| p.to_usize()))
        .collect();
    let sets = labelled_sets();

    match args.next() {
        None => {
            let countries: Vec<usize> = stowage
                .get_entity_interface::<InstCountries, QuickestBox>()
                .iter()
                .map(|c| c.to_usize())
                .collect();
            let scores = score_sets(&sets, &ids, &peers, &countries);
            print!("{}", ScoreTable::<N_PEERS>(&scores));
        }
        Some(name) => {
            let set = sets
                .iter()
                .find(|s| s.name == name)
                .unwrap_or_else(|| panic!("no peer set named {name}"));
            list_members(&stowage, set, &ids, &peers);
        }
    }
}

fn list_members(stowage: &Stowage, set: &PeerSet, ids: &HashMap<BigId, usize>, peers: &[PeerRow]) {
    let names: Vec<String> = stowage
        .get_marked_interface::<Institutions, NameMarker, ReadIter>()
        .collect();
    let rows = member_rows(set, ids);
    for row in set.members.iter().filter_map(|m| ids.get(m)) {
        println!("{}", names[*row]);
        for &peer in peers[*row].iter().filter(|&&p| p != 0) {
            let mark = if rows.contains(&peer) { '*' } else { ' ' };
            println!("  {mark} {}", names[peer]);
        }
    }
}
