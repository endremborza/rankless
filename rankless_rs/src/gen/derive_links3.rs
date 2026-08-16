use dmove::{Entity, MappableEntity, MarkedAttribute, NamespacedEntity, VariableSizeAttribute};

pub struct InstitutionsSemanticIds {}

pub struct CountriesSemanticIds {}

pub struct CountriesWorkCount {}

pub struct SourcesWorkCount {}

pub struct CountriesCitRankLadder {}

pub struct SourcesPeers {}

pub struct SubfieldsWorkCount {}

pub struct InstitutionsPeers {}

pub struct HitPapersCiteCounts {}

pub struct HitPapersDois {}

pub struct TopicsWorkCount {}

pub struct Coauthors {}

pub struct SourcesCitRankLadder {}

pub struct SubfieldsPeers {}

pub struct HitPapersBenchmarks {}

pub struct HitPapersWids {}

pub struct InstitutionsCitRankLadder {}

pub struct AuthorsPeers {}

pub struct SourcesSemanticIds {}

pub struct SubfieldsCitRankLadder {}

pub struct HitPapers {}

pub struct HitPapersNames {}

pub struct AuthorsWorkCount {}

pub struct AuthorsSemanticIds {}

pub struct CountriesPeers {}

pub struct AuthorsCitRankLadder {}

pub struct InstitutionsWorkCount {}

pub struct HitPapersCreatedTopic {}

pub struct SubfieldsSemanticIds {}

impl Entity for TopicsWorkCount {
    type T = u32;
    const N: usize = 4518;
    const NAME: &str = "topics-work-count";
}

impl MappableEntity for TopicsWorkCount {
    type KeyType = usize;
}

impl NamespacedEntity for TopicsWorkCount {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::WorkCountMarker> for crate::gen::a1_entity_mapping::Topics {
    type AttributeEntity = TopicsWorkCount;
}

impl Entity for HitPapers {
    type T = u32;
    const N: usize = 443023;
    const NAME: &str = "hit-papers";
}

impl MappableEntity for HitPapers {
    type KeyType = u64;
}

impl NamespacedEntity for HitPapers {
    const NS: &str = "derive_links3";
}

impl Entity for HitPapersNames {
    type T = String;
    const N: usize = 443023;
    const NAME: &str = "hit-papers-names";
}

impl MappableEntity for HitPapersNames {
    type KeyType = usize;
}

impl VariableSizeAttribute for HitPapersNames {
    type SizeType = u16;
    type LocType = u32;
}

impl NamespacedEntity for HitPapersNames {
    const NS: &str = "derive_links3";
}

impl Entity for HitPapersDois {
    type T = String;
    const N: usize = 443023;
    const NAME: &str = "hit-papers-dois";
}

impl MappableEntity for HitPapersDois {
    type KeyType = usize;
}

impl VariableSizeAttribute for HitPapersDois {
    type SizeType = u8;
    type LocType = u32;
}

impl NamespacedEntity for HitPapersDois {
    const NS: &str = "derive_links3";
}

impl Entity for HitPapersWids {
    type T = Box<[u32]>;
    const N: usize = 443023;
    const NAME: &str = "hit-papers-wids";
}

impl MappableEntity for HitPapersWids {
    type KeyType = usize;
}

impl VariableSizeAttribute for HitPapersWids {
    type SizeType = u8;
    type LocType = u32;
}

impl NamespacedEntity for HitPapersWids {
    const NS: &str = "derive_links3";
}

impl Entity for Coauthors {
    type T = Box<[(u32, u8)]>;
    const N: usize = 4256739;
    const NAME: &str = "coauthors";
}

impl MappableEntity for Coauthors {
    type KeyType = usize;
}

impl VariableSizeAttribute for Coauthors {
    type SizeType = u16;
    type LocType = u32;
}

impl NamespacedEntity for Coauthors {
    const NS: &str = "derive_links3";
}

impl Entity for HitPapersCiteCounts {
    type T = u32;
    const N: usize = 443023;
    const NAME: &str = "hit-papers-cite-counts";
}

impl MappableEntity for HitPapersCiteCounts {
    type KeyType = usize;
}

impl NamespacedEntity for HitPapersCiteCounts {
    const NS: &str = "derive_links3";
}

impl Entity for HitPapersBenchmarks {
    type T = u16;
    const N: usize = 443023;
    const NAME: &str = "hit-papers-benchmarks";
}

impl MappableEntity for HitPapersBenchmarks {
    type KeyType = usize;
}

impl NamespacedEntity for HitPapersBenchmarks {
    const NS: &str = "derive_links3";
}

impl Entity for HitPapersCreatedTopic {
    type T = u16;
    const N: usize = 443023;
    const NAME: &str = "hit-papers-created-topic";
}

impl MappableEntity for HitPapersCreatedTopic {
    type KeyType = usize;
}

impl NamespacedEntity for HitPapersCreatedTopic {
    const NS: &str = "derive_links3";
}

impl Entity for InstitutionsWorkCount {
    type T = u32;
    const N: usize = 37003;
    const NAME: &str = "institutions-work-count";
}

impl MappableEntity for InstitutionsWorkCount {
    type KeyType = usize;
}

impl NamespacedEntity for InstitutionsWorkCount {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::WorkCountMarker>
    for crate::gen::a1_entity_mapping::Institutions
{
    type AttributeEntity = InstitutionsWorkCount;
}

impl Entity for InstitutionsSemanticIds {
    type T = String;
    const N: usize = 37003;
    const NAME: &str = "institutions-semantic-ids";
}

impl MappableEntity for InstitutionsSemanticIds {
    type KeyType = usize;
}

impl VariableSizeAttribute for InstitutionsSemanticIds {
    type SizeType = u8;
    type LocType = u32;
}

impl NamespacedEntity for InstitutionsSemanticIds {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::SemanticIdMarker>
    for crate::gen::a1_entity_mapping::Institutions
{
    type AttributeEntity = InstitutionsSemanticIds;
}

impl Entity for SubfieldsWorkCount {
    type T = u32;
    const N: usize = 254;
    const NAME: &str = "subfields-work-count";
}

impl MappableEntity for SubfieldsWorkCount {
    type KeyType = usize;
}

impl NamespacedEntity for SubfieldsWorkCount {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::WorkCountMarker> for crate::gen::a1_entity_mapping::Subfields {
    type AttributeEntity = SubfieldsWorkCount;
}

impl Entity for SubfieldsSemanticIds {
    type T = String;
    const N: usize = 254;
    const NAME: &str = "subfields-semantic-ids";
}

impl MappableEntity for SubfieldsSemanticIds {
    type KeyType = usize;
}

impl VariableSizeAttribute for SubfieldsSemanticIds {
    type SizeType = u8;
    type LocType = u16;
}

impl NamespacedEntity for SubfieldsSemanticIds {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::SemanticIdMarker> for crate::gen::a1_entity_mapping::Subfields {
    type AttributeEntity = SubfieldsSemanticIds;
}

impl Entity for SourcesWorkCount {
    type T = u32;
    const N: usize = 44399;
    const NAME: &str = "sources-work-count";
}

impl MappableEntity for SourcesWorkCount {
    type KeyType = usize;
}

impl NamespacedEntity for SourcesWorkCount {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::WorkCountMarker> for crate::gen::a1_entity_mapping::Sources {
    type AttributeEntity = SourcesWorkCount;
}

impl Entity for SourcesSemanticIds {
    type T = String;
    const N: usize = 44399;
    const NAME: &str = "sources-semantic-ids";
}

impl MappableEntity for SourcesSemanticIds {
    type KeyType = usize;
}

impl VariableSizeAttribute for SourcesSemanticIds {
    type SizeType = u16;
    type LocType = u32;
}

impl NamespacedEntity for SourcesSemanticIds {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::SemanticIdMarker> for crate::gen::a1_entity_mapping::Sources {
    type AttributeEntity = SourcesSemanticIds;
}

impl Entity for AuthorsWorkCount {
    type T = u16;
    const N: usize = 4256739;
    const NAME: &str = "authors-work-count";
}

impl MappableEntity for AuthorsWorkCount {
    type KeyType = usize;
}

impl NamespacedEntity for AuthorsWorkCount {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::WorkCountMarker> for crate::gen::a1_entity_mapping::Authors {
    type AttributeEntity = AuthorsWorkCount;
}

impl Entity for AuthorsSemanticIds {
    type T = String;
    const N: usize = 4256739;
    const NAME: &str = "authors-semantic-ids";
}

impl MappableEntity for AuthorsSemanticIds {
    type KeyType = usize;
}

impl VariableSizeAttribute for AuthorsSemanticIds {
    type SizeType = u8;
    type LocType = u32;
}

impl NamespacedEntity for AuthorsSemanticIds {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::SemanticIdMarker> for crate::gen::a1_entity_mapping::Authors {
    type AttributeEntity = AuthorsSemanticIds;
}

impl Entity for CountriesWorkCount {
    type T = u32;
    const N: usize = 234;
    const NAME: &str = "countries-work-count";
}

impl MappableEntity for CountriesWorkCount {
    type KeyType = usize;
}

impl NamespacedEntity for CountriesWorkCount {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::WorkCountMarker> for crate::gen::a1_entity_mapping::Countries {
    type AttributeEntity = CountriesWorkCount;
}

impl Entity for CountriesSemanticIds {
    type T = String;
    const N: usize = 234;
    const NAME: &str = "countries-semantic-ids";
}

impl MappableEntity for CountriesSemanticIds {
    type KeyType = usize;
}

impl VariableSizeAttribute for CountriesSemanticIds {
    type SizeType = u8;
    type LocType = u16;
}

impl NamespacedEntity for CountriesSemanticIds {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::SemanticIdMarker> for crate::gen::a1_entity_mapping::Countries {
    type AttributeEntity = CountriesSemanticIds;
}

impl Entity for InstitutionsCitRankLadder {
    type T = [u32; 11];
    const N: usize = 253;
    const NAME: &str = "institutions-cit-rank-ladder";
}

impl MappableEntity for InstitutionsCitRankLadder {
    type KeyType = usize;
}

impl NamespacedEntity for InstitutionsCitRankLadder {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::CitRankLadderMarker>
    for crate::gen::a1_entity_mapping::Institutions
{
    type AttributeEntity = InstitutionsCitRankLadder;
}

impl Entity for InstitutionsPeers {
    type T = [u16; 10];
    const N: usize = 37003;
    const NAME: &str = "institutions-peers";
}

impl MappableEntity for InstitutionsPeers {
    type KeyType = usize;
}

impl NamespacedEntity for InstitutionsPeers {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::PeerMarker> for crate::gen::a1_entity_mapping::Institutions {
    type AttributeEntity = InstitutionsPeers;
}

impl Entity for SubfieldsCitRankLadder {
    type T = [u32; 11];
    const N: usize = 253;
    const NAME: &str = "subfields-cit-rank-ladder";
}

impl MappableEntity for SubfieldsCitRankLadder {
    type KeyType = usize;
}

impl NamespacedEntity for SubfieldsCitRankLadder {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::CitRankLadderMarker>
    for crate::gen::a1_entity_mapping::Subfields
{
    type AttributeEntity = SubfieldsCitRankLadder;
}

impl Entity for SubfieldsPeers {
    type T = [u8; 10];
    const N: usize = 254;
    const NAME: &str = "subfields-peers";
}

impl MappableEntity for SubfieldsPeers {
    type KeyType = usize;
}

impl NamespacedEntity for SubfieldsPeers {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::PeerMarker> for crate::gen::a1_entity_mapping::Subfields {
    type AttributeEntity = SubfieldsPeers;
}

impl Entity for CountriesCitRankLadder {
    type T = [u32; 11];
    const N: usize = 253;
    const NAME: &str = "countries-cit-rank-ladder";
}

impl MappableEntity for CountriesCitRankLadder {
    type KeyType = usize;
}

impl NamespacedEntity for CountriesCitRankLadder {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::CitRankLadderMarker>
    for crate::gen::a1_entity_mapping::Countries
{
    type AttributeEntity = CountriesCitRankLadder;
}

impl Entity for CountriesPeers {
    type T = [u8; 10];
    const N: usize = 234;
    const NAME: &str = "countries-peers";
}

impl MappableEntity for CountriesPeers {
    type KeyType = usize;
}

impl NamespacedEntity for CountriesPeers {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::PeerMarker> for crate::gen::a1_entity_mapping::Countries {
    type AttributeEntity = CountriesPeers;
}

impl Entity for SourcesCitRankLadder {
    type T = [u32; 11];
    const N: usize = 253;
    const NAME: &str = "sources-cit-rank-ladder";
}

impl MappableEntity for SourcesCitRankLadder {
    type KeyType = usize;
}

impl NamespacedEntity for SourcesCitRankLadder {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::CitRankLadderMarker>
    for crate::gen::a1_entity_mapping::Sources
{
    type AttributeEntity = SourcesCitRankLadder;
}

impl Entity for SourcesPeers {
    type T = [u16; 10];
    const N: usize = 44399;
    const NAME: &str = "sources-peers";
}

impl MappableEntity for SourcesPeers {
    type KeyType = usize;
}

impl NamespacedEntity for SourcesPeers {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::PeerMarker> for crate::gen::a1_entity_mapping::Sources {
    type AttributeEntity = SourcesPeers;
}

impl Entity for AuthorsCitRankLadder {
    type T = [u32; 11];
    const N: usize = 253;
    const NAME: &str = "authors-cit-rank-ladder";
}

impl MappableEntity for AuthorsCitRankLadder {
    type KeyType = usize;
}

impl NamespacedEntity for AuthorsCitRankLadder {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::CitRankLadderMarker>
    for crate::gen::a1_entity_mapping::Authors
{
    type AttributeEntity = AuthorsCitRankLadder;
}

impl Entity for AuthorsPeers {
    type T = [u32; 10];
    const N: usize = 4256739;
    const NAME: &str = "authors-peers";
}

impl MappableEntity for AuthorsPeers {
    type KeyType = usize;
}

impl NamespacedEntity for AuthorsPeers {
    const NS: &str = "derive_links3";
}

impl MarkedAttribute<crate::common::PeerMarker> for crate::gen::a1_entity_mapping::Authors {
    type AttributeEntity = AuthorsPeers;
}
