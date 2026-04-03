use dmove::{
    ByteFixArrayInterface, CompactEntity, MarkedAttribute, NamespacedEntity, UnsignedNumber, ET,
    MAA,
};

use crate::{
    common::{CitSubfieldsArrayMarker, YearlyPapersMarker},
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields},
        a2_init_atts::{InstCountries, InstLocs},
    },
    peers::{self, Embed2, PeerConfig},
    CiteCountMarker, QuickestBox, Stowage,
};

use super::{COORD_MIN_CITES, COORD_MIN_PAPERS};

// Entity-typed cit-subfields array aliases
pub(super) type InstCitSfsArr = ET<MAA<Institutions, CitSubfieldsArrayMarker>>;
pub(super) type SfCitSfsArr = ET<MAA<Subfields, CitSubfieldsArrayMarker>>;
pub(super) type CountryCitSfsArr = ET<MAA<Countries, CitSubfieldsArrayMarker>>;
pub(super) type SourceCitSfsArr = ET<MAA<Sources, CitSubfieldsArrayMarker>>;
pub(super) type AuthorCitSfsArr = ET<MAA<Authors, CitSubfieldsArrayMarker>>;

pub(super) struct InstPeerCtx {
    pub n: usize,
    pub filter: Vec<u8>,
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
    pub filter: Vec<u8>,
    pub embeds: Vec<[f32; 2]>,
    pub cit_sfs: Box<[AuthorCitSfsArr]>,
    pub top_sfs: Vec<[usize; peers::N_PEER_SF_DIMS]>,
    pub career_centroids: Vec<f32>,
    pub sf_weights: [f64; peers::N_PEER_SF_DIMS],
}

pub(super) struct SfPeerCtx {
    pub n: usize,
    pub filter: Vec<u8>,
    pub embeds: Vec<[f32; 2]>,
    pub cit_sfs: Box<[SfCitSfsArr]>,
    pub top_sfs: Vec<[usize; peers::N_PEER_SF_DIMS]>,
    pub sf_weights: [f64; peers::N_PEER_SF_DIMS],
}

pub(super) struct CountryPeerCtx {
    pub n: usize,
    pub filter: Vec<u8>,
    pub embeds: Vec<[f32; 2]>,
    pub cit_sfs: Box<[CountryCitSfsArr]>,
    pub top_sfs: Vec<[usize; peers::N_PEER_SF_DIMS]>,
    pub sf_weights: [f64; peers::N_PEER_SF_DIMS],
}

pub(super) struct SourcePeerCtx {
    pub n: usize,
    pub filter: Vec<u8>,
    pub embeds: Vec<[f32; 2]>,
    pub cit_sfs: Box<[SourceCitSfsArr]>,
    pub top_sfs: Vec<[usize; peers::N_PEER_SF_DIMS]>,
    pub sf_totals: Vec<f64>,
    pub sf_weights: [f64; peers::N_PEER_SF_DIMS],
}

// Builds [ln_cites, ln_papers] embeds (f64), normalizes, converts to f32.
fn build_embeds<E>(stowage: &Stowage, wcounts: &[usize], filter: &[u8]) -> Vec<[f32; 2]>
where
    E: MarkedAttribute<CiteCountMarker>,
    MAA<E, CiteCountMarker>: NamespacedEntity + CompactEntity,
    ET<MAA<E, CiteCountMarker>>: UnsignedNumber + ByteFixArrayInterface,
{
    let cites = stowage.get_marked_interface::<E, CiteCountMarker, QuickestBox>();
    let mut raw: Vec<[f64; 2]> = cites
        .iter()
        .enumerate()
        .map(|(i, &cc)| {
            [
                (cc.to_usize() as f64).max(COORD_MIN_CITES).ln(),
                (wcounts[i] as f64).max(COORD_MIN_PAPERS).ln(),
            ]
        })
        .collect();
    peers::normalize_2d_inplace(&mut raw, filter);
    raw.iter().map(|&e| [e[0] as f32, e[1] as f32]).collect()
}

impl InstPeerCtx {
    pub(super) fn new(stowage: &Stowage, filter: Vec<u8>, wcounts: &[usize]) -> Self {
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
    pub(super) fn new(stowage: &Stowage, filter: Vec<u8>, wcounts: &[usize]) -> Self {
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
    pub(super) fn new(stowage: &Stowage, filter: Vec<u8>, wcounts: &[usize]) -> Self {
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
    pub(super) fn new(stowage: &Stowage, filter: Vec<u8>, wcounts: &[usize]) -> Self {
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
    pub fn new<const N: usize>(
        stowage: &Stowage,
        filter: Vec<u8>,
        wcounts: &[usize],
        yearly_papers: &[[u32; N]],
    ) -> Self {
        let embeds = build_embeds::<Authors>(stowage, wcounts, &filter);
        let n = embeds.len();
        let cit_sfs =
            stowage.get_marked_interface::<Authors, CitSubfieldsArrayMarker, QuickestBox>();
        let top_sfs = peers::compute_top_sfs(&*cit_sfs);
        let career_centroids = peers::compute_career_centroids(yearly_papers, &filter);
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
