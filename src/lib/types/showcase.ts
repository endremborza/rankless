import type { EntityAttsForLinks, Paper } from '$lib/tree-types';

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

export type ShowcasePeers = {
	subfields: { name: string; cites: number }[];
	yearFrom: number; // calendar year of yearly[0]
	yearly: number[];
};

export type ShowcaseSamplePaper = {
	paper: Paper;
	entityAtts: EntityAttsForLinks;
	discAuthorNames: Record<string, string>;
};

export type ShowcaseData = {
	scholar: ShowcaseScholar;
	coauthors: ShowcaseCoauthors;
	peers: ShowcasePeers;
	samplePaper: ShowcaseSamplePaper | null;
};
