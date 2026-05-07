use dmove::{MappableEntity, NamespacedEntity, MarkedAttribute, VariableSizeAttribute, Entity};

pub struct HitPaperYearlyCitations { }

pub struct HitPapersTopPaperAuthors { }

pub struct HitPapersEra { }

pub struct HitPapersTopPaperSubfields { }

pub struct HitPapersTopJournals { }

pub struct HitPapersTopCitingSubfields { }

impl Entity for HitPapersEra { type T = [u32; 11]; const N: usize = 401674; const NAME: & str = "hit-papers-era"; }

impl MappableEntity for HitPapersEra { type KeyType = usize; }

impl NamespacedEntity for HitPapersEra { const NS: & str = "derive_links5"; }

impl MarkedAttribute<crate::common::YearlyCitationsMarker> for crate::gen::derive_links3::HitPapers { type AttributeEntity = HitPapersEra; }

impl Entity for HitPaperYearlyCitations { type T = Box<[u32]>; const N: usize = 401674; const NAME: & str = "hit-paper-yearly-citations"; }

impl MappableEntity for HitPaperYearlyCitations { type KeyType = usize; }

impl VariableSizeAttribute for HitPaperYearlyCitations { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for HitPaperYearlyCitations { const NS: & str = "derive_links5"; }

impl Entity for HitPapersTopJournals { type T = [(u32, u16); 3]; const N: usize = 401674; const NAME: & str = "hit-papers-top-journals"; }

impl MappableEntity for HitPapersTopJournals { type KeyType = usize; }

impl NamespacedEntity for HitPapersTopJournals { const NS: & str = "derive_links5"; }

impl MarkedAttribute<crate::common::Top3JournalMarker> for crate::gen::derive_links3::HitPapers { type AttributeEntity = HitPapersTopJournals; }

impl Entity for HitPapersTopPaperAuthors { type T = [(u32, u32); 25]; const N: usize = 401674; const NAME: & str = "hit-papers-top-paper-authors"; }

impl MappableEntity for HitPapersTopPaperAuthors { type KeyType = usize; }

impl NamespacedEntity for HitPapersTopPaperAuthors { const NS: & str = "derive_links5"; }

impl MarkedAttribute<crate::common::Top15AuthorMarker> for crate::gen::derive_links3::HitPapers { type AttributeEntity = HitPapersTopPaperAuthors; }

impl Entity for HitPapersTopPaperSubfields { type T = [(u32, u8); 3]; const N: usize = 401674; const NAME: & str = "hit-papers-top-paper-subfields"; }

impl MappableEntity for HitPapersTopPaperSubfields { type KeyType = usize; }

impl NamespacedEntity for HitPapersTopPaperSubfields { const NS: & str = "derive_links5"; }

impl MarkedAttribute<crate::common::Top3PaperSfMarker> for crate::gen::derive_links3::HitPapers { type AttributeEntity = HitPapersTopPaperSubfields; }

impl Entity for HitPapersTopCitingSubfields { type T = [(u32, u8); 3]; const N: usize = 401674; const NAME: & str = "hit-papers-top-citing-subfields"; }

impl MappableEntity for HitPapersTopCitingSubfields { type KeyType = usize; }

impl NamespacedEntity for HitPapersTopCitingSubfields { const NS: & str = "derive_links5"; }

impl MarkedAttribute<crate::common::Top3CitingSfMarker> for crate::gen::derive_links3::HitPapers { type AttributeEntity = HitPapersTopCitingSubfields; }