use std::{io, sync::Arc};

use dmove::{reverse_prefixed_n, MarkedAttribute, UnsignedNumber, VarAttBuilder, ET};
use hashbrown::HashMap;

use crate::{
    common::{
        init_empty_slice, EmptyAttributeEntity, HitWorkMarker, Top15AuthorMarker,
        Top3AffCountryMarker, Top3CitingSfMarker, Top3JournalMarker, Top3PaperSfMarker,
        Top3PaperTopicMarker, YearlyCitationsMarker, YearlyPapersMarker, NET,
    },
    env_consts::FINAL_YEAR,
    gen::{
        a1_entity_mapping::{Authors, Countries, Sources, Subfields, Topics},
        derive_links2::WorkTopSource,
        derive_links3::HitPapers,
    },
    steps::{
        a1_entity_mapping::YearInterface,
        derive_links2::{inc_year, CiteDeriver, EraRec, Top15Rec, Top3Rec},
    },
    QuickestBox, QuickestNumbered, Stowage, WorkCountMarker,
};

macro_rules! mark_empty {
    ($marked:ident, $($marker:ident => $marker_type:ty),*) =>
    {
        $(
            impl MarkedAttribute<$marker> for $marked {
                type AttributeEntity = EmptyAttributeEntity<$marker_type>;
            }
        )*
    };
}

mark_empty!(
    HitPapers,
    WorkCountMarker => u8,
    YearlyPapersMarker => EraRec,
    HitWorkMarker => Box<[ET<HitPapers>]>,
    Top3AffCountryMarker => Top3Rec<Countries>,
    Top3PaperTopicMarker => Top3Rec<Topics>
);

impl CiteDeriver {
    fn hit_paper_atts(&self) {
        let mut cy_counts = init_empty_slice::<HitPapers, Box<[u32]>>();
        let mut cy_eras = init_empty_slice::<HitPapers, EraRec>();
        let mut top3_journals = init_empty_slice::<HitPapers, Top3Rec<Sources>>();
        let mut top15_authors = init_empty_slice::<HitPapers, Top15Rec<Authors>>();
        let mut top3_paper_sfs = init_empty_slice::<HitPapers, Top3Rec<Subfields>>();
        let mut top3_citing_sfs = init_empty_slice::<HitPapers, Top3Rec<Subfields>>();
        self.stowage
            .get_entity_interface::<HitPapers, QuickestNumbered>()
            .0
            .iter()
            .for_each(|(wid, hwid)| {
                let wu = wid.to_usize();
                let hi = hwid.to_usize();
                let wyear = self.backends.year[wu];
                let mut v = vec![0; (1 + FINAL_YEAR - YearInterface::reverse(wyear)).to_usize()];
                let mut era = EraRec::default();
                let citing = self.backends.wciting.get(&wu).expect("cites for work");
                citing.iter().for_each(|cw| {
                    let cyear = self.backends.year[cw.to_usize()];
                    if cyear >= wyear {
                        v[(cyear - wyear).to_usize()] += 1;
                    }
                    inc_year(&mut era, cyear);
                });
                cy_eras[hi] = era;
                cy_counts[hi] = v.into_boxed_slice();

                let src = self.w_top_source[wu];
                if src.to_usize() != 0 {
                    top3_journals[hi][0] = (citing.len() as u32, src);
                }

                let mut sf_counts: HashMap<usize, u32> = HashMap::new();
                for sf_id in self.backends.wsubfields.get(&wu).unwrap() {
                    *sf_counts.entry(*sf_id as usize).or_insert(0) += 1;
                }
                let mut sf_vec: Vec<(usize, u32)> = sf_counts.into_iter().collect();
                sf_vec.sort_unstable_by(|a, b| b.1.cmp(&a.1));
                for (k, (sfid, score)) in sf_vec.iter().take(3).enumerate() {
                    top3_paper_sfs[hi][k] = (*score, NET::<Subfields>::from_usize(*sfid));
                }

                let mut csf_counts: HashMap<usize, u32> = HashMap::new();
                for cw in citing {
                    for sf_id in self.backends.wsubfields.get(&cw.to_usize()).unwrap() {
                        *csf_counts.entry(*sf_id as usize).or_insert(0) += 1;
                    }
                }
                let mut csf_vec: Vec<(usize, u32)> = csf_counts.into_iter().collect();
                csf_vec.sort_unstable_by(|a, b| b.1.cmp(&a.1));
                for (k, (sfid, score)) in csf_vec.iter().take(3).enumerate() {
                    top3_citing_sfs[hi][k] = (*score, NET::<Subfields>::from_usize(*sfid));
                }

                let coauthships = self.backends.w_aships.get(&wu).unwrap();
                let ccn = coauthships.len().max(1) as f64;
                let cite_weight = citing.len() as f64 / ccn;
                let mut authors: Vec<(f64, NET<Authors>)> = coauthships
                    .iter()
                    .filter_map(|any_ship_id| {
                        let (is_filtered, ship_id) = reverse_prefixed_n(any_ship_id.to_usize());
                        if is_filtered {
                            Some((cite_weight, self.backends.ship_fa[ship_id]))
                        } else {
                            None
                        }
                    })
                    .collect();
                authors.sort_unstable_by(|a, b| {
                    b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal)
                });
                for (k, (score, aid)) in authors.iter().take(25).enumerate() {
                    top15_authors[hi][k] = (*score as u32, *aid);
                }
            });
        self.stowage
            .ditf::<YearlyCitationsMarker, HitPapers, _>(cy_eras.into_vec(), "era");
        self.stowage.add_iter_owned::<VarAttBuilder, _, _>(
            cy_counts.to_vec().into_iter(),
            Some("hit-paper-yearly-citations"),
        );
        self.stowage
            .ditf::<Top3JournalMarker, HitPapers, _>(top3_journals.into_vec(), "top-journals");
        self.stowage
            .ditf::<Top15AuthorMarker, HitPapers, _>(top15_authors.into_vec(), "top-paper-authors");
        self.stowage.ditf::<Top3PaperSfMarker, HitPapers, _>(
            top3_paper_sfs.into_vec(),
            "top-paper-subfields",
        );
        self.stowage.ditf::<Top3CitingSfMarker, HitPapers, _>(
            top3_citing_sfs.into_vec(),
            "top-citing-subfields",
        );
    }
}

pub fn main(stowage: Stowage) -> io::Result<()> {
    let wts = stowage.get_entity_interface::<WorkTopSource, QuickestBox>();
    let cd = CiteDeriver::new(stowage, wts);
    cd.hit_paper_atts();
    let sarc = Arc::new(cd.stowage);
    Arc::try_unwrap(sarc).ok().unwrap().write_code()?;
    Ok(())
}
