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
	| 'collab-nation'
	| 'paper-journals'
	| 'paper-authors';

export type View = {
	name: string;
	citations: number;
	papers: number;
	dmId: number;
	primeRelations: RelatedEntity[];
	similars: SearchResult[];
	authorNetwork: number[];
	instRels: InstRel[];
	startYear: number;
	yearlyPapers: number[];
	yearlyCites: number[];
	meta?: Record<string, string>;
};
export type RelatedEntity = {
	name: string,
	semanticId: string,
	etype: EntityType,
	relType: number,
	score: number,
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

export type RootType = 'authors' | 'institutions' | 'sources' | 'countries' | 'subfields' | 'hit-papers';
export type EntityType = RootType | 'works' | 'topics' | 'qs';
export type SearchResult = {
	name: string;
	semanticId: string;
	rootType: RootType;
	papers: number;
	citations: number;
	distinctText?: string;
};

export type SubbedRel = { desc: string; subs: RelatedEntity[] };
export type AboutPara = {
	prefix: string;
	postText: string;
	topRels: SubbedRel[];
	footText: string,
}

export type TreeResponse = { tree: ResponseNode; atts: AttributeLabels, shallowed: boolean };
export type TopsResponse = { name: RootType; entities: SearchResult[] }[];
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

export type PeerAuthorEntry = {
	name: string;
	semanticId: string;
	papers: number;
	citations: number;
	subfieldCitations: number[];
	yearlyPapers: number[];
	yearlyCites: number[];
	startYear: number;
};

export type AuthorPeersResp = {
	topSubfields: PeerSubfield[];
	peers: PeerAuthorEntry[];
	hero: PeerAuthorEntry;
};
