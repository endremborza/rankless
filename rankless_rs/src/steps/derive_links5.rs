use std::io;

use dmove::{MarkedAttribute, UnsignedNumber, VarAttBuilder, ET};

use crate::{
    common::{
        init_empty_slice, EmptyAttributeEntity, HitWorkMarker, Top15AuthorMarker,
        Top3AffCountryMarker, Top3CitingSfMarker, Top3JournalMarker, Top3PaperSfMarker,
        Top3PaperTopicMarker, YearlyCitationsMarker, YearlyPapersMarker,
    },
    env_consts::FINAL_YEAR,
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics},
        a2_init_atts::{CountryCodes, CountryCodesThree},
        derive_links2::WorkTopSource,
        derive_links3::HitPapers,
    },
    steps::{
        a1_entity_mapping::YearInterface,
        derive_links2::{inc_year, CiteDeriver, EraRec, Top15Rec, Top3Rec},
    },
    QuickestBox, QuickestNumbered, ReadFixIter, Stowage, WorkCountMarker,
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
    Top3JournalMarker => Top3Rec<Sources>,
    Top15AuthorMarker => Top15Rec<Authors>,
    Top3AffCountryMarker => Top3Rec<Countries>,
    Top3PaperTopicMarker => Top3Rec<Topics>,
    Top3CitingSfMarker => Top3Rec<Subfields>,
    Top3PaperSfMarker => Top3Rec<Subfields>
);

impl Stowage {
    fn write_all_sem_ids(&self) {
        self.write_semantic_id::<Authors>();
        self.write_semantic_id::<Institutions>();
        self.write_semantic_id::<Sources>();
        self.write_semantic_id::<Subfields>();
        let citer = self
            .get_entity_interface::<CountryCodesThree, ReadFixIter>()
            .zip(self.get_entity_interface::<CountryCodes, ReadFixIter>())
            .map(|(e3, e2)| {
                if e3 != [0; 3] {
                    String::from_utf8(e3.into()).unwrap().to_lowercase()
                } else {
                    String::from_utf8(e2.into()).unwrap().to_lowercase()
                }
            });
        self.decsem::<Countries, _>(citer);
    }
}

impl CiteDeriver {
    fn hit_paper_atts(&self) {
        let mut cy_counts = init_empty_slice::<HitPapers, Box<[u32]>>();
        let mut cy_eras = init_empty_slice::<HitPapers, EraRec>();
        self.stowage
            .get_entity_interface::<HitPapers, QuickestNumbered>()
            .0
            .iter()
            .for_each(|(wid, hwid)| {
                let wu = wid.to_usize();
                let wyear = self.backends.year[wu];
                let mut v = vec![0; (1 + FINAL_YEAR - YearInterface::reverse(wyear)).to_usize()];
                let mut era = EraRec::default();
                self.backends
                    .wciting
                    .get(&wu)
                    .expect("cites for work")
                    .iter()
                    .for_each(|cw| {
                        let cyear = self.backends.year[cw.to_usize()];
                        if cyear >= wyear {
                            v[(cyear - wyear).to_usize()] += 1;
                        }
                        inc_year(&mut era, cyear);
                    });
                cy_eras[hwid.to_usize()] = era;
                cy_counts[hwid.to_usize()] = v.into_boxed_slice();
            });
        self.stowage
            .ditf::<YearlyCitationsMarker, HitPapers, _>(cy_eras.into_vec(), "era");
        self.stowage.add_iter_owned::<VarAttBuilder, _, _>(
            cy_counts.to_vec().into_iter(),
            Some("hit-paper-yearly-citations"),
        );
    }
}

pub fn main(stowage: Stowage) -> io::Result<()> {
    let wts = stowage.get_entity_interface::<WorkTopSource, QuickestBox>();
    let cd = CiteDeriver::new(stowage, wts);
    cd.hit_paper_atts();
    cd.stowage.write_all_sem_ids();
    cd.stowage.write_code()?;
    Ok(())
}
