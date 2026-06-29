// Shape of the baked homepage snapshot (src/lib/assets/data/homepage-showcase.json),
// produced by pyscripts/homepage_showcase.py. Imported directly by the showcase component,
// so the home page needs no backend call to render the feature previews.

export type ShowcaseScholar = {
	name: string;
	semanticId: string;
	papers: number;
	citations: number;
};

export type ShowcaseCoauthor = { name: string; semanticId: string; score: number };

export type ShowcaseCoauthors = {
	rootName: string;
	nodes: ShowcaseCoauthor[];
	// [i, j, weight] over the nodes above (papers co-authored between the pair).
	edges: number[][];
};

// One hit paper as the rainbow draws it: an arc from `year` to now, height by `citations`.
export type ShowcaseHitPaper = { year: number; citations: number; name: string };

// One mark on a co-author's timeline row: their shared papers with the hero in a given year.
export type ShowcaseTimelineMark = { year: number; n: number; hit: boolean };

export type ShowcaseTimelineRow = {
	name: string;
	firstYear: number;
	lastYear: number;
	marks: ShowcaseTimelineMark[];
};

export type ShowcaseTimeline = {
	yearLo: number;
	yearHi: number;
	rows: ShowcaseTimelineRow[];
};

export type ShowcasePeers = {
	heroName: string;
	peerName: string;
	peerCountry: string | null;
	// Top fields by hero citations, both sides' counts for the side-by-side comparison.
	subfields: { name: string; hero: number; peer: number }[];
	yearFrom: number; // calendar year of *Yearly[0]
	heroYearly: number[];
	peerYearly: number[];
};

export type ShowcaseData = {
	scholar: ShowcaseScholar;
	hitPapers: ShowcaseHitPaper[];
	coauthorTimeline: ShowcaseTimeline;
	coauthors: ShowcaseCoauthors;
	peers: ShowcasePeers;
};
