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
export type View = {
	name: string;
	citations: number;
	papers: number;
	dmId: number;
	primeRelations: RelatedEntity[],
	similars: SearchResult[];
	// sfCoords: [number, number];
	instRels: InstRel[];
	startYear: number,
	yearlyPapers: number[],
	yearlyCites: number[],
};
export type RelatedEntity = {
	name: string,
	semanticId: string,
	etype: EntityType,
	relType: number,
	score: number,
}
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
};

export type RootType = 'authors' | 'institutions' | 'sources' | 'countries' | 'subfields';
export type EntityType = RootType | 'works' | 'topics';
export type SearchResult = {
	name: string;
	id: string;
	semanticId: string;
	rootType: RootType;
	papers: number;
	citations: number;
};
export type TreeResponse = { tree: ResponseNode; atts: AttributeLabels };
export type TreeSpec = {
	rootType: RootType;
	breakdowns: BreakdownSpec[];
	defaultIsSpec: boolean;
};
export type TreeSpecs = { specs: Record<RootType, TreeSpec[]>; yearBreaks: number[] };

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

export type InteractionKind = 'toggle-select' | 'highlight' | 'de-highlight';
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
