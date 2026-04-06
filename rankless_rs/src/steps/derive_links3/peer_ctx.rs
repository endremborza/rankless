use core::f32;

use dmove::{
    ByteFixArrayInterface, CompactEntity, Entity, MarkedAttribute, NamespacedEntity,
    UnsignedNumber, ET, MAA,
};

use crate::{
    common::{init_empty_slice, CitSubfieldsArrayMarker},
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields},
        a2_init_atts::{InstCountries, InstLocs, WorkYears},
        derive_links2::AuthorWorks,
    },
    peers::{self, Embed2, PeerConfig},
    steps::a1_entity_mapping::Years,
    CiteCountMarker, QuickestBox, ReadIter, Stowage,
};

use super::{COORD_MIN_CITES, COORD_MIN_PAPERS};

pub const N_PEER_SF_DIMS: usize = 10;
pub const W_PEER_SF: f64 = 1.0;
pub const W_PEER_RATE: f64 = 0.5;
pub const W_PEER_GEO: f64 = 0.3;
pub const W_PEER_COUNTRY: f64 = 0.5;
pub const W_PEER_TEMPORAL: f64 = 0.4;

const N_DECILES: usize = 20;
const K_TREE: usize = 500;

// Entity-typed cit-subfields array aliases
pub(super) type InstCitSfsArr = ET<MAA<Institutions, CitSubfieldsArrayMarker>>;
pub(super) type SfCitSfsArr = ET<MAA<Subfields, CitSubfieldsArrayMarker>>;
pub(super) type CountryCitSfsArr = ET<MAA<Countries, CitSubfieldsArrayMarker>>;
pub(super) type SourceCitSfsArr = ET<MAA<Sources, CitSubfieldsArrayMarker>>;
pub(super) type AuthorCitSfsArr = ET<MAA<Authors, CitSubfieldsArrayMarker>>;

pub(super) struct InstPeerCtx {
    pub n: usize,
    pub filter: Vec<bool>,
    pub embeds: Vec<[f32; 2]>,
    pub cit_sfs: Box<[InstCitSfsArr]>,
    pub top_sfs: Vec<[usize; peers::N_PEER_SF_DIMS]>,
    pub sf_totals: Vec<f64>,
    pub locs: Box<[(f64, f64)]>,
    pub countries: Box<[ET<InstCountries>]>,
    pub sf_weights: [f64; peers::N_PEER_SF_DIMS],
}

pub struct AuthorPeerCtx {
    pub n: usize,
    pub filter: Vec<bool>,
    pub embeds: Vec<[f32; 2]>,
    pub cit_sfs: Box<[AuthorCitSfsArr]>,
    pub top_sfs: Vec<[usize; peers::N_PEER_SF_DIMS]>,
    pub career_centroids: Vec<f32>,
    pub sf_weights: [f64; peers::N_PEER_SF_DIMS],
}

pub(super) struct SfPeerCtx {
    pub n: usize,
    pub filter: Vec<bool>,
    pub embeds: Vec<[f32; 2]>,
    pub cit_sfs: Box<[SfCitSfsArr]>,
    pub top_sfs: Vec<[usize; peers::N_PEER_SF_DIMS]>,
    pub sf_weights: [f64; peers::N_PEER_SF_DIMS],
}

pub(super) struct CountryPeerCtx {
    pub n: usize,
    pub filter: Vec<bool>,
    pub embeds: Vec<[f32; 2]>,
    pub cit_sfs: Box<[CountryCitSfsArr]>,
    pub top_sfs: Vec<[usize; peers::N_PEER_SF_DIMS]>,
    pub sf_weights: [f64; peers::N_PEER_SF_DIMS],
}

pub(super) struct SourcePeerCtx {
    pub n: usize,
    pub filter: Vec<bool>,
    pub embeds: Vec<[f32; 2]>,
    pub cit_sfs: Box<[SourceCitSfsArr]>,
    pub top_sfs: Vec<[usize; peers::N_PEER_SF_DIMS]>,
    pub sf_totals: Vec<f64>,
    pub sf_weights: [f64; peers::N_PEER_SF_DIMS],
}

fn build_embeds<E>(stowage: &Stowage, wcounts: &[usize], filter: &[bool]) -> Vec<[f32; 2]>
where
    E: MarkedAttribute<CiteCountMarker>,
    MAA<E, CiteCountMarker>: NamespacedEntity + CompactEntity,
    ET<MAA<E, CiteCountMarker>>: UnsignedNumber + ByteFixArrayInterface,
{
    let cites = stowage.get_marked_interface::<E, CiteCountMarker, QuickestBox>();
    let raw: Vec<[Option<f32>; 2]> = cites
        .iter()
        .enumerate()
        .map(|(i, &cc)| {
            if filter[i] {
                [
                    Some((cc.to_usize() as f64).max(COORD_MIN_CITES).ln() as f32),
                    Some((wcounts[i] as f64).max(COORD_MIN_PAPERS).ln() as f32),
                ]
            } else {
                [None, None]
            }
        })
        .collect();
    peers::normalize_opt_arr(raw)
}

impl InstPeerCtx {
    pub(super) fn new(stowage: &Stowage, filter: Vec<bool>, wcounts: &[usize]) -> Self {
        let embeds = build_embeds::<Institutions>(stowage, wcounts, &filter);
        let n = embeds.len();
        let cit_sfs =
            stowage.get_marked_interface::<Institutions, CitSubfieldsArrayMarker, QuickestBox>();
        let top_sfs = peers::compute_top_sfs(&*cit_sfs);
        let sf_totals = peers::compute_sf_totals(&*cit_sfs);
        let locs = stowage.get_entity_interface::<InstLocs, QuickestBox>();
        let countries = stowage.get_entity_interface::<InstCountries, QuickestBox>();
        Self {
            n,
            filter,
            embeds,
            cit_sfs,
            top_sfs,
            sf_totals,
            locs,
            countries,
            sf_weights: peers::sf_peer_weights(),
        }
    }
}

impl SfPeerCtx {
    pub(super) fn new(stowage: &Stowage, filter: Vec<bool>, wcounts: &[usize]) -> Self {
        let embeds = build_embeds::<Subfields>(stowage, wcounts, &filter);
        let n = embeds.len();
        let cit_sfs =
            stowage.get_marked_interface::<Subfields, CitSubfieldsArrayMarker, QuickestBox>();
        let top_sfs = peers::compute_top_sfs(&*cit_sfs);
        Self {
            n,
            filter,
            embeds,
            cit_sfs,
            top_sfs,
            sf_weights: peers::sf_peer_weights(),
        }
    }
}

impl CountryPeerCtx {
    pub(super) fn new(stowage: &Stowage, filter: Vec<bool>, wcounts: &[usize]) -> Self {
        let embeds = build_embeds::<Countries>(stowage, wcounts, &filter);
        let n = embeds.len();
        let cit_sfs =
            stowage.get_marked_interface::<Countries, CitSubfieldsArrayMarker, QuickestBox>();
        let top_sfs = peers::compute_top_sfs(&*cit_sfs);
        Self {
            n,
            filter,
            embeds,
            cit_sfs,
            top_sfs,
            sf_weights: peers::sf_peer_weights(),
        }
    }
}

impl SourcePeerCtx {
    pub(super) fn new(stowage: &Stowage, filter: Vec<bool>, wcounts: &[usize]) -> Self {
        let embeds = build_embeds::<Sources>(stowage, wcounts, &filter);
        let n = embeds.len();
        let cit_sfs =
            stowage.get_marked_interface::<Sources, CitSubfieldsArrayMarker, QuickestBox>();
        let top_sfs = peers::compute_top_sfs(&*cit_sfs);
        let sf_totals = peers::compute_sf_totals(&*cit_sfs);
        Self {
            n,
            filter,
            embeds,
            cit_sfs,
            top_sfs,
            sf_totals,
            sf_weights: peers::sf_peer_weights(),
        }
    }
}

impl AuthorPeerCtx {
    pub fn new(
        stowage: &Stowage,
        filter: Vec<bool>,
        wcounts: &[usize],
        w_years: Box<[ET<WorkYears>]>,
    ) -> Self {
        let embeds = build_embeds::<Authors>(stowage, wcounts, &filter);
        let n = embeds.len();
        let cit_sfs =
            stowage.get_marked_interface::<Authors, CitSubfieldsArrayMarker, QuickestBox>();
        let top_sfs = peers::compute_top_sfs(&*cit_sfs);
        let mut career_centroids_o = init_empty_slice::<Authors, [Option<f32>; 1]>();
        for (aid, aworks) in stowage
            .get_entity_interface::<AuthorWorks, ReadIter>()
            .enumerate()
        {
            let mut yearly_papers = [0; Years::N + 1];
            for wid in aworks {
                let wind = w_years[wid.to_usize()].to_usize();
                yearly_papers[wind] += 1;
            }
            career_centroids_o[aid] = [peers::compute_career_centroid(&yearly_papers)];
        }
        let career_centroids = peers::normalize_opt_arr(career_centroids_o.to_vec())
            .into_iter()
            .map(|e| e[0])
            .collect();
        Self {
            n,
            filter,
            embeds,
            cit_sfs,
            top_sfs,
            career_centroids,
            sf_weights: peers::sf_peer_weights(),
        }
    }
}

impl PeerConfig for InstPeerCtx {
    type E = Institutions;
    type Point = Embed2;

    fn n(&self) -> usize {
        self.n
    }
    fn filter(&self) -> &[u8] {
        &self.filter
    }
    fn rank_val(&self, idx: usize) -> f32 {
        self.embeds[idx][0]
    }
    fn point(&self, idx: usize) -> Embed2 {
        Embed2 {
            coords: self.embeds[idx],
            dm_id: idx,
        }
    }
    fn n_deciles(&self) -> usize {
        10
    }

    fn dist(&self, a: usize, b: usize) -> f64 {
        let w = &self.sf_weights;
        peers::W_PEER_SF
            * peers::sf_log_dist(&self.cit_sfs[a], &self.cit_sfs[b], &self.top_sfs[a], w)
            + peers::W_PEER_RATE
                * peers::sf_rate_dist(
                    &self.cit_sfs[a],
                    &self.cit_sfs[b],
                    &self.top_sfs[a],
                    self.sf_totals[a],
                    self.sf_totals[b],
                )
            + peers::W_PEER_GEO * peers::geo_sq_dist(self.locs[a], self.locs[b])
            + peers::W_PEER_COUNTRY
                * if self.countries[a] != self.countries[b] {
                    1.0
                } else {
                    0.0
                }
    }
}

impl PeerConfig for SfPeerCtx {
    type E = Subfields;
    type Point = Embed2;

    fn n(&self) -> usize {
        self.n
    }
    fn filter(&self) -> &[u8] {
        &self.filter
    }
    fn rank_val(&self, idx: usize) -> f32 {
        self.embeds[idx][0]
    }
    fn point(&self, idx: usize) -> Embed2 {
        Embed2 {
            coords: self.embeds[idx],
            dm_id: idx,
        }
    }
    fn n_deciles(&self) -> usize {
        1
    }

    fn dist(&self, a: usize, b: usize) -> f64 {
        peers::W_PEER_SF
            * peers::sf_log_dist(
                &self.cit_sfs[a],
                &self.cit_sfs[b],
                &self.top_sfs[a],
                &self.sf_weights,
            )
    }
}

impl PeerConfig for CountryPeerCtx {
    type E = Countries;
    type Point = Embed2;

    fn n(&self) -> usize {
        self.n
    }
    fn filter(&self) -> &[u8] {
        &self.filter
    }
    fn rank_val(&self, idx: usize) -> f32 {
        self.embeds[idx][0]
    }
    fn point(&self, idx: usize) -> Embed2 {
        Embed2 {
            coords: self.embeds[idx],
            dm_id: idx,
        }
    }
    fn n_deciles(&self) -> usize {
        1
    }

    fn dist(&self, a: usize, b: usize) -> f64 {
        peers::W_PEER_SF
            * peers::sf_log_dist(
                &self.cit_sfs[a],
                &self.cit_sfs[b],
                &self.top_sfs[a],
                &self.sf_weights,
            )
    }
}

impl PeerConfig for SourcePeerCtx {
    type E = Sources;
    type Point = Embed2;

    fn n(&self) -> usize {
        self.n
    }
    fn filter(&self) -> &[u8] {
        &self.filter
    }
    fn rank_val(&self, idx: usize) -> f32 {
        self.embeds[idx][0]
    }
    fn point(&self, idx: usize) -> Embed2 {
        Embed2 {
            coords: self.embeds[idx],
            dm_id: idx,
        }
    }
    fn n_deciles(&self) -> usize {
        10
    }

    fn dist(&self, a: usize, b: usize) -> f64 {
        let w = &self.sf_weights;
        peers::W_PEER_SF
            * peers::sf_log_dist(&self.cit_sfs[a], &self.cit_sfs[b], &self.top_sfs[a], w)
            + peers::W_PEER_RATE
                * peers::sf_rate_dist(
                    &self.cit_sfs[a],
                    &self.cit_sfs[b],
                    &self.top_sfs[a],
                    self.sf_totals[a],
                    self.sf_totals[b],
                )
    }
}

impl PeerConfig for AuthorPeerCtx {
    type E = Authors;
    type Point = Embed2;

    fn n(&self) -> usize {
        self.n
    }
    fn filter(&self) -> &[u8] {
        &self.filter
    }
    fn rank_val(&self, idx: usize) -> f32 {
        self.embeds[idx][0]
    }
    fn point(&self, idx: usize) -> Embed2 {
        Embed2 {
            coords: self.embeds[idx],
            dm_id: idx,
        }
    }

    fn dist(&self, a: usize, b: usize) -> f64 {
        peers::W_PEER_SF
            * peers::sf_log_dist(
                &self.cit_sfs[a],
                &self.cit_sfs[b],
                &self.top_sfs[a],
                &self.sf_weights,
            )
            + peers::W_PEER_TEMPORAL
                * (self.career_centroids[a] - self.career_centroids[b]).powi(2) as f64
    }
}
