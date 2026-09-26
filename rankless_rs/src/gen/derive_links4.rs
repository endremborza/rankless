use dmove::{Entity, MappableEntity, MarkedAttribute, NamespacedEntity, VariableSizeAttribute};

pub struct CountriesWeightedPaperScore {}

pub struct SourcesScoredPaperCount {}

pub struct AuthorCitingHitsDirect {}

pub struct CountriesHits {}

pub struct InstitutionsTopMeanPaperScore {}

pub struct InstitutionsHits {}

pub struct TopicsHits {}

pub struct AuthorsScoredPaperCount {}

pub struct SourcesHIndex {}

pub struct SubfieldsHIndexSince {}

pub struct SubfieldsScoredPaperCount {}

pub struct InstitutionsHIndexSince {}

pub struct SourcesTopMeanPaperScore {}

pub struct AuthorsHIndex {}

pub struct HitPapersPeers {}

pub struct CountriesScoredPaperCount {}

pub struct InstitutionsWeightedPaperScore {}

pub struct CountriesHIndex {}

pub struct CountriesHIndexSince {}

pub struct SubfieldsHIndex {}

pub struct AuthorsWeightedPaperScore {}

pub struct AuthorsHits {}

pub struct InstitutionsScoredPaperCount {}

pub struct HitPapersSemanticIds {}

pub struct HitPapersCitRankLadder {}

pub struct InstitutionsHIndex {}

pub struct CountriesTopMeanPaperScore {}

pub struct AuthorsTopMeanPaperScore {}

pub struct SubfieldsHits {}

pub struct SourcesHIndexSince {}

pub struct SourcesHits {}

pub struct AuthorCitingHitsOnce {}

impl Entity for CountriesScoredPaperCount {
    type T = u32;
    const N: usize = 235;
    const NAME: &str = "countries-scored-paper-count";
}

impl MappableEntity for CountriesScoredPaperCount {
    type KeyType = usize;
}

impl NamespacedEntity for CountriesScoredPaperCount {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::ScoredPaperCountMarker>
    for crate::gen::a1_entity_mapping::Countries
{
    type AttributeEntity = CountriesScoredPaperCount;
}

impl Entity for CountriesHIndex {
    type T = u32;
    const N: usize = 235;
    const NAME: &str = "countries-h-index";
}

impl MappableEntity for CountriesHIndex {
    type KeyType = usize;
}

impl NamespacedEntity for CountriesHIndex {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HIndexMarker> for crate::gen::a1_entity_mapping::Countries {
    type AttributeEntity = CountriesHIndex;
}

impl Entity for CountriesHIndexSince {
    type T = [u32; 2];
    const N: usize = 235;
    const NAME: &str = "countries-h-index-since";
}

impl MappableEntity for CountriesHIndexSince {
    type KeyType = usize;
}

impl NamespacedEntity for CountriesHIndexSince {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HIndexSinceMarker>
    for crate::gen::a1_entity_mapping::Countries
{
    type AttributeEntity = CountriesHIndexSince;
}

impl Entity for CountriesWeightedPaperScore {
    type T = f32;
    const N: usize = 235;
    const NAME: &str = "countries-weighted-paper-score";
}

impl MappableEntity for CountriesWeightedPaperScore {
    type KeyType = usize;
}

impl NamespacedEntity for CountriesWeightedPaperScore {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::WeightedPaperScoreMarker>
    for crate::gen::a1_entity_mapping::Countries
{
    type AttributeEntity = CountriesWeightedPaperScore;
}

impl Entity for CountriesTopMeanPaperScore {
    type T = f32;
    const N: usize = 235;
    const NAME: &str = "countries-top-mean-paper-score";
}

impl MappableEntity for CountriesTopMeanPaperScore {
    type KeyType = usize;
}

impl NamespacedEntity for CountriesTopMeanPaperScore {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::TopMeanPaperScoreMarker>
    for crate::gen::a1_entity_mapping::Countries
{
    type AttributeEntity = CountriesTopMeanPaperScore;
}

impl Entity for SubfieldsScoredPaperCount {
    type T = u32;
    const N: usize = 254;
    const NAME: &str = "subfields-scored-paper-count";
}

impl MappableEntity for SubfieldsScoredPaperCount {
    type KeyType = usize;
}

impl NamespacedEntity for SubfieldsScoredPaperCount {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::ScoredPaperCountMarker>
    for crate::gen::a1_entity_mapping::Subfields
{
    type AttributeEntity = SubfieldsScoredPaperCount;
}

impl Entity for SubfieldsHIndex {
    type T = u32;
    const N: usize = 254;
    const NAME: &str = "subfields-h-index";
}

impl MappableEntity for SubfieldsHIndex {
    type KeyType = usize;
}

impl NamespacedEntity for SubfieldsHIndex {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HIndexMarker> for crate::gen::a1_entity_mapping::Subfields {
    type AttributeEntity = SubfieldsHIndex;
}

impl Entity for SubfieldsHIndexSince {
    type T = [u32; 2];
    const N: usize = 254;
    const NAME: &str = "subfields-h-index-since";
}

impl MappableEntity for SubfieldsHIndexSince {
    type KeyType = usize;
}

impl NamespacedEntity for SubfieldsHIndexSince {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HIndexSinceMarker>
    for crate::gen::a1_entity_mapping::Subfields
{
    type AttributeEntity = SubfieldsHIndexSince;
}

impl Entity for SourcesScoredPaperCount {
    type T = u32;
    const N: usize = 43604;
    const NAME: &str = "sources-scored-paper-count";
}

impl MappableEntity for SourcesScoredPaperCount {
    type KeyType = usize;
}

impl NamespacedEntity for SourcesScoredPaperCount {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::ScoredPaperCountMarker>
    for crate::gen::a1_entity_mapping::Sources
{
    type AttributeEntity = SourcesScoredPaperCount;
}

impl Entity for SourcesHIndex {
    type T = u32;
    const N: usize = 43604;
    const NAME: &str = "sources-h-index";
}

impl MappableEntity for SourcesHIndex {
    type KeyType = usize;
}

impl NamespacedEntity for SourcesHIndex {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HIndexMarker> for crate::gen::a1_entity_mapping::Sources {
    type AttributeEntity = SourcesHIndex;
}

impl Entity for SourcesHIndexSince {
    type T = [u32; 2];
    const N: usize = 43604;
    const NAME: &str = "sources-h-index-since";
}

impl MappableEntity for SourcesHIndexSince {
    type KeyType = usize;
}

impl NamespacedEntity for SourcesHIndexSince {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HIndexSinceMarker> for crate::gen::a1_entity_mapping::Sources {
    type AttributeEntity = SourcesHIndexSince;
}

impl Entity for SourcesTopMeanPaperScore {
    type T = f32;
    const N: usize = 43604;
    const NAME: &str = "sources-top-mean-paper-score";
}

impl MappableEntity for SourcesTopMeanPaperScore {
    type KeyType = usize;
}

impl NamespacedEntity for SourcesTopMeanPaperScore {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::TopMeanPaperScoreMarker>
    for crate::gen::a1_entity_mapping::Sources
{
    type AttributeEntity = SourcesTopMeanPaperScore;
}

impl Entity for InstitutionsScoredPaperCount {
    type T = u32;
    const N: usize = 37532;
    const NAME: &str = "institutions-scored-paper-count";
}

impl MappableEntity for InstitutionsScoredPaperCount {
    type KeyType = usize;
}

impl NamespacedEntity for InstitutionsScoredPaperCount {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::ScoredPaperCountMarker>
    for crate::gen::a1_entity_mapping::Institutions
{
    type AttributeEntity = InstitutionsScoredPaperCount;
}

impl Entity for InstitutionsHIndex {
    type T = u32;
    const N: usize = 37532;
    const NAME: &str = "institutions-h-index";
}

impl MappableEntity for InstitutionsHIndex {
    type KeyType = usize;
}

impl NamespacedEntity for InstitutionsHIndex {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HIndexMarker> for crate::gen::a1_entity_mapping::Institutions {
    type AttributeEntity = InstitutionsHIndex;
}

impl Entity for InstitutionsHIndexSince {
    type T = [u32; 2];
    const N: usize = 37532;
    const NAME: &str = "institutions-h-index-since";
}

impl MappableEntity for InstitutionsHIndexSince {
    type KeyType = usize;
}

impl NamespacedEntity for InstitutionsHIndexSince {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HIndexSinceMarker>
    for crate::gen::a1_entity_mapping::Institutions
{
    type AttributeEntity = InstitutionsHIndexSince;
}

impl Entity for InstitutionsWeightedPaperScore {
    type T = f32;
    const N: usize = 37532;
    const NAME: &str = "institutions-weighted-paper-score";
}

impl MappableEntity for InstitutionsWeightedPaperScore {
    type KeyType = usize;
}

impl NamespacedEntity for InstitutionsWeightedPaperScore {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::WeightedPaperScoreMarker>
    for crate::gen::a1_entity_mapping::Institutions
{
    type AttributeEntity = InstitutionsWeightedPaperScore;
}

impl Entity for InstitutionsTopMeanPaperScore {
    type T = f32;
    const N: usize = 37532;
    const NAME: &str = "institutions-top-mean-paper-score";
}

impl MappableEntity for InstitutionsTopMeanPaperScore {
    type KeyType = usize;
}

impl NamespacedEntity for InstitutionsTopMeanPaperScore {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::TopMeanPaperScoreMarker>
    for crate::gen::a1_entity_mapping::Institutions
{
    type AttributeEntity = InstitutionsTopMeanPaperScore;
}

impl Entity for AuthorsScoredPaperCount {
    type T = u32;
    const N: usize = 4321023;
    const NAME: &str = "authors-scored-paper-count";
}

impl MappableEntity for AuthorsScoredPaperCount {
    type KeyType = usize;
}

impl NamespacedEntity for AuthorsScoredPaperCount {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::ScoredPaperCountMarker>
    for crate::gen::a1_entity_mapping::Authors
{
    type AttributeEntity = AuthorsScoredPaperCount;
}

impl Entity for AuthorsHIndex {
    type T = u32;
    const N: usize = 4321023;
    const NAME: &str = "authors-h-index";
}

impl MappableEntity for AuthorsHIndex {
    type KeyType = usize;
}

impl NamespacedEntity for AuthorsHIndex {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HIndexMarker> for crate::gen::a1_entity_mapping::Authors {
    type AttributeEntity = AuthorsHIndex;
}

impl Entity for AuthorsWeightedPaperScore {
    type T = f32;
    const N: usize = 4321023;
    const NAME: &str = "authors-weighted-paper-score";
}

impl MappableEntity for AuthorsWeightedPaperScore {
    type KeyType = usize;
}

impl NamespacedEntity for AuthorsWeightedPaperScore {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::WeightedPaperScoreMarker>
    for crate::gen::a1_entity_mapping::Authors
{
    type AttributeEntity = AuthorsWeightedPaperScore;
}

impl Entity for AuthorsTopMeanPaperScore {
    type T = f32;
    const N: usize = 4321023;
    const NAME: &str = "authors-top-mean-paper-score";
}

impl MappableEntity for AuthorsTopMeanPaperScore {
    type KeyType = usize;
}

impl NamespacedEntity for AuthorsTopMeanPaperScore {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::TopMeanPaperScoreMarker>
    for crate::gen::a1_entity_mapping::Authors
{
    type AttributeEntity = AuthorsTopMeanPaperScore;
}

impl Entity for CountriesHits {
    type T = Box<[u32]>;
    const N: usize = 235;
    const NAME: &str = "countries-hits";
}

impl MappableEntity for CountriesHits {
    type KeyType = usize;
}

impl VariableSizeAttribute for CountriesHits {
    type SizeType = u32;
    type LocType = u32;
}

impl NamespacedEntity for CountriesHits {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HitWorkMarker> for crate::gen::a1_entity_mapping::Countries {
    type AttributeEntity = CountriesHits;
}

impl Entity for InstitutionsHits {
    type T = Box<[u32]>;
    const N: usize = 37532;
    const NAME: &str = "institutions-hits";
}

impl MappableEntity for InstitutionsHits {
    type KeyType = usize;
}

impl VariableSizeAttribute for InstitutionsHits {
    type SizeType = u16;
    type LocType = u32;
}

impl NamespacedEntity for InstitutionsHits {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HitWorkMarker> for crate::gen::a1_entity_mapping::Institutions {
    type AttributeEntity = InstitutionsHits;
}

impl Entity for SourcesHits {
    type T = Box<[u32]>;
    const N: usize = 43604;
    const NAME: &str = "sources-hits";
}

impl MappableEntity for SourcesHits {
    type KeyType = usize;
}

impl VariableSizeAttribute for SourcesHits {
    type SizeType = u32;
    type LocType = u32;
}

impl NamespacedEntity for SourcesHits {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HitWorkMarker> for crate::gen::a1_entity_mapping::Sources {
    type AttributeEntity = SourcesHits;
}

impl Entity for SubfieldsHits {
    type T = Box<[u32]>;
    const N: usize = 254;
    const NAME: &str = "subfields-hits";
}

impl MappableEntity for SubfieldsHits {
    type KeyType = usize;
}

impl VariableSizeAttribute for SubfieldsHits {
    type SizeType = u16;
    type LocType = u32;
}

impl NamespacedEntity for SubfieldsHits {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HitWorkMarker> for crate::gen::a1_entity_mapping::Subfields {
    type AttributeEntity = SubfieldsHits;
}

impl Entity for TopicsHits {
    type T = Box<[u32]>;
    const N: usize = 4518;
    const NAME: &str = "topics-hits";
}

impl MappableEntity for TopicsHits {
    type KeyType = usize;
}

impl VariableSizeAttribute for TopicsHits {
    type SizeType = u16;
    type LocType = u32;
}

impl NamespacedEntity for TopicsHits {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HitWorkMarker> for crate::gen::a1_entity_mapping::Topics {
    type AttributeEntity = TopicsHits;
}

impl Entity for AuthorsHits {
    type T = Box<[u32]>;
    const N: usize = 4321023;
    const NAME: &str = "authors-hits";
}

impl MappableEntity for AuthorsHits {
    type KeyType = usize;
}

impl VariableSizeAttribute for AuthorsHits {
    type SizeType = u16;
    type LocType = u32;
}

impl NamespacedEntity for AuthorsHits {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::HitWorkMarker> for crate::gen::a1_entity_mapping::Authors {
    type AttributeEntity = AuthorsHits;
}

impl Entity for AuthorCitingHitsDirect {
    type T = Box<[u32]>;
    const N: usize = 4321023;
    const NAME: &str = "author-citing-hits-direct";
}

impl MappableEntity for AuthorCitingHitsDirect {
    type KeyType = usize;
}

impl VariableSizeAttribute for AuthorCitingHitsDirect {
    type SizeType = u8;
    type LocType = u32;
}

impl NamespacedEntity for AuthorCitingHitsDirect {
    const NS: &str = "derive_links4";
}

impl Entity for AuthorCitingHitsOnce {
    type T = Box<[u32]>;
    const N: usize = 4321023;
    const NAME: &str = "author-citing-hits-once";
}

impl MappableEntity for AuthorCitingHitsOnce {
    type KeyType = usize;
}

impl VariableSizeAttribute for AuthorCitingHitsOnce {
    type SizeType = u8;
    type LocType = u8;
}

impl NamespacedEntity for AuthorCitingHitsOnce {
    const NS: &str = "derive_links4";
}

impl Entity for HitPapersSemanticIds {
    type T = String;
    const N: usize = 401744;
    const NAME: &str = "hit-papers-semantic-ids";
}

impl MappableEntity for HitPapersSemanticIds {
    type KeyType = usize;
}

impl VariableSizeAttribute for HitPapersSemanticIds {
    type SizeType = u8;
    type LocType = u32;
}

impl NamespacedEntity for HitPapersSemanticIds {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::SemanticIdMarker> for crate::gen::derive_links3::HitPapers {
    type AttributeEntity = HitPapersSemanticIds;
}

impl Entity for HitPapersPeers {
    type T = [u32; 10];
    const N: usize = 401744;
    const NAME: &str = "hit-papers-peers";
}

impl MappableEntity for HitPapersPeers {
    type KeyType = usize;
}

impl NamespacedEntity for HitPapersPeers {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::PeerMarker> for crate::gen::derive_links3::HitPapers {
    type AttributeEntity = HitPapersPeers;
}

impl Entity for HitPapersCitRankLadder {
    type T = [u32; 11];
    const N: usize = 253;
    const NAME: &str = "hit-papers-cit-rank-ladder";
}

impl MappableEntity for HitPapersCitRankLadder {
    type KeyType = usize;
}

impl NamespacedEntity for HitPapersCitRankLadder {
    const NS: &str = "derive_links4";
}

impl MarkedAttribute<crate::common::CitRankLadderMarker> for crate::gen::derive_links3::HitPapers {
    type AttributeEntity = HitPapersCitRankLadder;
}
