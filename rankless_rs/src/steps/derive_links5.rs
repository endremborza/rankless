use std::{
    cmp::Ordering,
    fmt::Debug,
    hash::Hash,
    io,
    iter::Enumerate,
    mem::replace,
    ops::AddAssign,
    sync::Arc,
    thread::{self, JoinHandle},
};

use dmove::{
    reverse_prefixed_n, ByteFixArrayInterface, DowncastingBuilder, Entity, FixAttBuilder,
    MarkedAttribute, NamespacedEntity, UnsignedNumber, VarAttBuilder, VarAttIterator,
    VariableSizeAttribute, VattArrPair, ET, MAA,
};
use dmove_macro::ByteFixArrayInterface;
use hashbrown::{HashMap, HashSet};
use tqdm::{Iter, Tqdm};

use crate::{
    common::{
        init_empty_slice, BeS, CitSubfieldsArrayMarker, EmptyAttributeEntity, HitWorkMarker,
        InstRelMarker, MainWorkMarker, QuickAttPair, QuickMap, RefSubfieldsArrayMarker,
        Top15AuthorMarker, Top3AffCountryMarker, Top3CitingSfMarker, Top3JournalMarker,
        Top3PaperSfMarker, Top3PaperTopicMarker, WorkLoader, YearlyCitationsMarker,
        YearlyPapersMarker,
    },
    env_consts::{FINAL_YEAR, START_YEAR},
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{
            AuthorshipFilteredAuthor, CountryCodes, CountryCodesThree,
            FilteredAuthorshipInstitutions, InstCountries, SourceYearQs, WorkAnyAuthorships,
            WorkSources, WorkTopics, WorkYears,
        },
        derive_links1::{WorkInstitutions, WorkSubfields},
        derive_links2::{WorkCountries, WorkTopSource},
        derive_links3::HitPapers,
    },
    make_interface_struct,
    oa_structs::{
        post::{Institution, Source},
        FieldLike, NamedEntity,
    },
    semantic_ids::SemCsvObj,
    steps::a1_entity_mapping::{Qs, YearInterface, Years},
    CiteCountMarker, QuickestBox, QuickestNumbered, ReadFixIter, ReadIter, Stowage,
    WorkCountMarker,
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

pub fn main(stowage: Stowage) -> io::Result<()> {
    hit_paper_atts(&self);
    Ok(())
}

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
