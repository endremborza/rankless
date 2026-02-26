use dmove::{MappableEntity, NamespacedEntity, MarkedAttribute, VariableSizeAttribute, Entity};

pub struct HitPaperYearlyCitations { }

pub struct CountriesSemanticIds { }

pub struct SourcesSemanticIds { }

pub struct HitPapersEra { }

pub struct InstitutionsSemanticIds { }

pub struct SubfieldsSemanticIds { }

pub struct AuthorsSemanticIds { }

impl Entity for HitPapersEra { type T = [u32; 11]; const N: usize = 137936; const NAME: & str = "hit-papers-era"; }

impl MappableEntity for HitPapersEra { type KeyType = usize; }

impl NamespacedEntity for HitPapersEra { const NS: & str = "derive_links5"; }

impl MarkedAttribute<crate::common::YearlyCitationsMarker> for crate::gen::derive_links3::HitPapers { type AttributeEntity = HitPapersEra; }

impl Entity for HitPaperYearlyCitations { type T = Box<[u32]>; const N: usize = 137936; const NAME: & str = "hit-paper-yearly-citations"; }

impl MappableEntity for HitPaperYearlyCitations { type KeyType = usize; }

impl VariableSizeAttribute for HitPaperYearlyCitations { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for HitPaperYearlyCitations { const NS: & str = "derive_links5"; }

impl Entity for AuthorsSemanticIds { type T = String; const N: usize = 4156381; const NAME: & str = "authors-semantic-ids"; }

impl MappableEntity for AuthorsSemanticIds { type KeyType = usize; }

impl VariableSizeAttribute for AuthorsSemanticIds { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for AuthorsSemanticIds { const NS: & str = "derive_links5"; }

impl MarkedAttribute<crate::common::SemanticIdMarker> for crate::gen::a1_entity_mapping::Authors { type AttributeEntity = AuthorsSemanticIds; }

impl Entity for InstitutionsSemanticIds { type T = String; const N: usize = 31861; const NAME: & str = "institutions-semantic-ids"; }

impl MappableEntity for InstitutionsSemanticIds { type KeyType = usize; }

impl VariableSizeAttribute for InstitutionsSemanticIds { type SizeType = u8; type LocType = u32; }

impl NamespacedEntity for InstitutionsSemanticIds { const NS: & str = "derive_links5"; }

impl MarkedAttribute<crate::common::SemanticIdMarker> for crate::gen::a1_entity_mapping::Institutions { type AttributeEntity = InstitutionsSemanticIds; }

impl Entity for SourcesSemanticIds { type T = String; const N: usize = 40769; const NAME: & str = "sources-semantic-ids"; }

impl MappableEntity for SourcesSemanticIds { type KeyType = usize; }

impl VariableSizeAttribute for SourcesSemanticIds { type SizeType = u16; type LocType = u32; }

impl NamespacedEntity for SourcesSemanticIds { const NS: & str = "derive_links5"; }

impl MarkedAttribute<crate::common::SemanticIdMarker> for crate::gen::a1_entity_mapping::Sources { type AttributeEntity = SourcesSemanticIds; }

impl Entity for SubfieldsSemanticIds { type T = String; const N: usize = 254; const NAME: & str = "subfields-semantic-ids"; }

impl MappableEntity for SubfieldsSemanticIds { type KeyType = usize; }

impl VariableSizeAttribute for SubfieldsSemanticIds { type SizeType = u8; type LocType = u16; }

impl NamespacedEntity for SubfieldsSemanticIds { const NS: & str = "derive_links5"; }

impl MarkedAttribute<crate::common::SemanticIdMarker> for crate::gen::a1_entity_mapping::Subfields { type AttributeEntity = SubfieldsSemanticIds; }

impl Entity for CountriesSemanticIds { type T = String; const N: usize = 233; const NAME: & str = "countries-semantic-ids"; }

impl MappableEntity for CountriesSemanticIds { type KeyType = usize; }

impl VariableSizeAttribute for CountriesSemanticIds { type SizeType = u8; type LocType = u16; }

impl NamespacedEntity for CountriesSemanticIds { const NS: & str = "derive_links5"; }

impl MarkedAttribute<crate::common::SemanticIdMarker> for crate::gen::a1_entity_mapping::Countries { type AttributeEntity = CountriesSemanticIds; }