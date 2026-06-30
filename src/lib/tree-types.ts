export type OMap<T> = Record<string, T>;
export type PathInTree = number[];
export type TreeGen<T> = T & { children?: Record<number, TreeGen<T>> };

export type InstRel = {
	start: number;
	end: number;
	papers: number;
	citations: number;
	semId: string;
	name: string;
};

export type RelTypes =
	| 'paper-fields'
	| 'citing-fields'
	| 'paper-topics'
	| 'citing-topics'
	| 'collab-nation'
	| 'paper-journals'
	| 'paper-authors';

export type DominatedTopic = { name: string; sharePct: number };
export type View = {
	name: string;
	citations: number;
	papers: number;
	dmId: number;
	relations: Record<RelTypes, RelatedEntity[]>;
	similars: SearchResult[];
	authorNetwork: number[];
	instRels: InstRel[];
	startYear: number;
	yearlyPapers: number[];
	yearlyCites: number[];
	meta?: Record<string, string>;
};
export type RelatedEntity = {
	name: string;
	semanticId: string;
	etype: EntityType;
	score: number;
	// Shared-paper count, only present on an author hero's co-authors (papers co-authored with them).
	count?: number;
	// Topic relations carry their parent subfield ("field" in the UI) so the hero can nest them.
	parentName?: string;
	parentSemanticId?: string;
};
export type SelectionOption = {
	name: string;
	id: string;
	rootType: string;
};
export type ShareSpec = { year: number; treeId: number; selectionState: BareNode };
export type FullTreeConfig = {
	year: number;
	treeId: number;
	rootType: RootType;
	semanticId: string;
	wide: boolean;
};
export type PaperAuthorship = {
	author: string; // "F{id}" for filtered, "D{id}" for discarded
	insts: number[];
};

export type PaperBiblio = {
	volume: string;
	issue: string;
	first_page: string;
	last_page: string;
};

export type Paper = {
	wid: number;
	oaId: number;
	year: number;
	name: string;
	doi: string;
	citations: number;
	source: number;
	authorships: PaperAuthorship[];
	yearlyCites?: number[];
	biblio?: PaperBiblio;
	isHit: boolean;
	hitBm?: number;
	hitSemId?: string;
	createdTopic?: string;
};

export type EntityAttLabel = { name: string; semantic_id: string; spec_baseline: number };
export type EntityAttsForLinks = Record<string, Record<string, EntityAttLabel>>;

export type AuthorMeta = { prize: number; year: number };

export type PaperSetResp = {
	papers: Paper[];
	entityAtts: EntityAttsForLinks;
	discAuthorNames: Record<string, string>;
	authorsMeta: Record<string, AuthorMeta>;
};

export type PaperProfileResp = {
	dag: RefTree;
	papers: PaperSetResp;
};

export type AuthorMergeRequest = {
	other_semantic_id: string;
	note: string | null;
	created_at: string;
};

export type RootType =
	| 'authors'
	| 'institutions'
	| 'sources'
	| 'countries'
	| 'subfields'
	| 'hit-papers';
export type EntityType = RootType | 'works' | 'topics' | 'qs';
export type SearchResult = {
	name: string;
	semanticId: string;
	rootType: RootType;
	papers: number;
	citations: number;
	// Total (unfiltered) OpenAlex citations; present only for authors.
	rawCites?: number;
	distinctText?: string;
	oaId?: number;
	dmId?: number;
};

export type SubbedRel = { desc: string; subs: RelatedEntity[] };
export type AboutPara = {
	prefix: string;
	postText: string;
	topRels: SubbedRel[];
	footText: string;
};

export type TreeResponse = { tree: ResponseNode; atts: AttributeLabels; shallowed: boolean };
export type TopsResponse = { name: RootType; entities: SearchResult[] }[];
export type CountsResponse = {
	entities: { name: RootType; count: number }[];
	total_citations: number;
	total_works: number;
};
export type TreeSpec = {
	rootType: RootType;
	breakdowns: BreakdownSpec[];
	defaultIsSpec: boolean;
};
export type TreeSpecs = { specs: Record<RootType, TreeSpec[]>; yearBreaks: number[] };
export type IndsByEntityType = Record<EntityType, number[]>;
export type LevelT = OMap<{ w: number; id: number }>;

export type BreakdownSpec = {
	attributeType: RootType;
	specDenomInd: number;
	sourceSide: boolean;
};

export type AttributeLabel = { name: string; specBaseline: number; oaId?: number };
export type AttributeLabels = Record<EntityType, OMap<AttributeLabel>>;

export type BareNode = TreeGen<object>;

export type ResponseNode = TreeGen<{
	linkCount: number;
	sourceCount: number;
	topSourceId: number;
	topSourceLinks: number;
}>;

export type WeightedNode = TreeGen<{
	weight: number;
	source_count: number;
	top_source: [number, number];
}>;
export type NamedNode = TreeGen<{ weight: number; name: string }>;
export type EmbeddedNode = TreeGen<{
	weight: number;
	name: string;
	totalOffsetOnLevel: OffsetInfo;
	childrenSumWeight: number;
	totalOffsetAmongSiblings: OffsetInfo;
	isSelected: boolean;
	scaleEnds: { min: number; max: number; mid: number };
}>;

export type OffsetInfo = { rank: number; weight: number };

export type InteractionKind = 'toggle-select' | 'highlight' | 'arm' | 'disarm';
type SizeBaseKind = 'volume' | 'specialization';

export type TreeInteractionEvent = {
	path: PathInTree;
	action: InteractionKind;
	topLeftCorner: { x: number; y: number };
};

export type DerivedLevelInfo = { totalWeight: number; totalNodes: number };

export type TreeInfo = { tree: EmbeddedNode; meta: DerivedLevelInfo[] };
export type ControlSpec = {
	exclude: number[];
	include: number[];
	limit: number;
	showTop: boolean;
	sizeBase: SizeBaseKind;
};
export type FullControlSpecs = {
	levelSpecs: ControlSpec[];
	globalSizeBase: SizeBaseKind;
	globalLimit: number;
};

export type BreakdownOptions = OMap<{ children: BreakdownOptions; treeSpecs: number[] }>;
export type SelectedBreakdowns = string[];
export type LevelOutSpec = {
	totalSize: number;
	topOffset: number;
	isVisible: boolean;
	levelOptions: string[];
};

export type RefTree = 'Leaf' | { Node: Record<number, RefTree> };

export type PathToPaperResp = {
	tree: RefTree;
	doi: string;
	title: string;
	year: number;
};

export type PathResp = {
	paths: PathToPaperResp[];
	srcName: string;
	targetName: string;
	relWorks: number[];
	nameMap: Record<number, string>;
	doiMap: Record<number, string>;
};

export type PaginatedPaperSetResp = {
	resp: PaperSetResp;
	totalPapers: number;
	sliceStart: number;
};

export type OaPaperResp = {
	title: string;
	doi: string;
	abstract: string;
	year: number;
	authors: { name: string; link: string; institutions: string[] }[];
};

export type PeerSubfield = {
	name: string;
	semanticId: string;
	dmId: number;
};

export type PeerEntry = {
	name: string;
	semanticId: string;
	papers: number;
	citations: number;
	subfieldCitations: number[];
	yearlyPapers: number[];
	yearlyCites: number[];
	startYear: number;
	hIndex?: number;
	yearCentroid?: number;
	country: string | null;
};

// The hero's papers per subfield (production side), one entry per nonzero subfield — lets a field
// tile pulled in by a top topic (one outside the top paper-fields) still show its paper count.
export type RefSubfield = { semanticId: string; papers: number };

export type EntityPeersResp = {
	topSubfields: PeerSubfield[];
	refSubfields: RefSubfield[];
	peers: PeerEntry[];
	hero: PeerEntry;
};

// Rank-breakpoint table for one root type (cached per type). `ladder[subfieldDmId]` holds the
// citation threshold at each percentile band; null where the cohort is too small.
export type LadderData = {
	pctBands: number[];
	ladder: (number | null)[][];
};
