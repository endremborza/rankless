use dmove::{Entity, EntityMutableMapperBackend, UnsignedNumber};

use hashbrown::HashMap;

use crate::{
    interfacing::Getters,
    io::{
        AttributeLabel, AttributeLabelOut, AttributeLabels, BreakdownSpec, BufSerChildren,
        BufSerTree, FullTreeQuery, ManFileHandle, TreeBasisState,
    },
};
use rankless_rs::gen::a1_entity_mapping::{Institutions, Works};

pub type AttributeLabelUnion = HashMap<String, Box<[AttributeLabel]>>;

pub fn get_atts(
    tree: &BufSerTree,
    bds: &[BreakdownSpec],
    state: &TreeBasisState,
    fh: &mut ManFileHandle,
    fq: &FullTreeQuery,
) -> AttributeLabels {
    let eid = fq.ck.eid;
    let etype = &fq.name;

    let mut atts = HashMap::new();
    let eatts = atts.entry(etype.to_string()).or_insert(HashMap::new());
    add_leaves(vec![eid as u32].iter(), eatts, fh, &etype, state);
    ext_atts(&mut atts, tree, bds, fh, state);
    atts
}

pub fn add_nonwork_label<'a, I, N>(
    eids: I,
    eatts: &mut HashMap<usize, AttributeLabelOut>,
    etype: &str,
    state: &TreeBasisState,
) where
    I: Iterator<Item = &'a N>,
    N: UnsignedNumber + 'a,
{
    if let Some(u_eatts) = state.att_union.get(etype) {
        if etype == Institutions::NAME {
            eids.for_each(|k| {
                let ku = k.to_usize();
                eatts.insert(ku, oaify_inst(&u_eatts[ku], &state.gets, ku));
            })
        } else {
            eids.for_each(|k| {
                eatts.insert(k.to_usize(), to_none_alabel(&u_eatts[k.to_usize()]));
            })
        };
    } else {
        //Qs might not be here
        // println!("WARNING: {etype} not found in attribute union");
    }
}

fn ext_atts(
    atts: &mut AttributeLabels,
    tree: &BufSerTree,
    bds: &[BreakdownSpec],
    work_map: &mut ManFileHandle,
    state: &TreeBasisState,
) {
    let at = &bds[0].attribute_type;
    let eatts = atts.entry(at.to_string()).or_insert(HashMap::new());
    match tree.children.as_ref() {
        BufSerChildren::Leaves(leaves) => add_leaves(leaves.keys(), eatts, work_map, at, state),
        BufSerChildren::Nodes(nodes) => {
            add_leaves(nodes.keys(), eatts, work_map, at, state);
            nodes
                .values()
                .for_each(|v| ext_atts(atts, v, &bds[1..], work_map, state))
        }
    };
}

fn add_leaves<'a, I>(
    leaves: I,
    eatts: &mut HashMap<usize, AttributeLabelOut>,
    work_map: &mut ManFileHandle,
    etype: &str,
    state: &TreeBasisState,
) where
    I: Iterator<Item = &'a u32>,
{
    if etype == Works::NAME {
        leaves.for_each(|k| {
            eatts.insert(
                k.to_usize(),
                AttributeLabelOut {
                    name: work_map
                        .get_via_mut(&k.to_usize())
                        .unwrap_or("Unknown".to_string()),
                    spec_baseline: 1.0,
                    oa_id: None,
                },
            );
        });
    } else {
        add_nonwork_label(leaves, eatts, etype, state);
    }
}

fn oaify_inst(v: &AttributeLabel, gets: &Getters, id: usize) -> AttributeLabelOut {
    AttributeLabelOut {
        spec_baseline: v.spec_baseline,
        name: v.name.to_string(),
        oa_id: Some(gets.inst_oa[id]),
    }
}

fn to_none_alabel(v: &AttributeLabel) -> AttributeLabelOut {
    AttributeLabelOut {
        spec_baseline: v.spec_baseline,
        name: v.name.to_string(),
        oa_id: None,
    }
}
