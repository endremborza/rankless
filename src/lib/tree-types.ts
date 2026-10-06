import type {
	PostAttRelatedEntity,
	RelationGroups,
	SearchResult
} from './wire/rankless_server/responses';
import type { CollapsedNodeJson } from './wire/rankless_trees/io';
import type { RefDAG } from './wire/rankless_trees/path_finder';

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

export type RelTypes = keyof RelationGroups;

export type DominatedTopic = { name: string; sharePct: number };
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
// An entity as a list names it — what a picker, a chip label or a ladder lookup needs of it.
export type NamedEntity = Pick<SearchResult, 'name' | 'semanticId' | 'dmId'>;
// A search result with the root type it lives under, which a single-type list leaves implicit.
export type RootedResult = SearchResult & { rootType: RootType };

export type SubbedRel = { desc: string; subs: PostAttRelatedEntity[] };
export type AboutPara = {
	prefix: string;
	postText: string;
	topRels: SubbedRel[];
	footText: string;
};

export type IndsByEntityType = Record<EntityType, number[]>;
export type LevelT = OMap<{ w: number; id: number }>;

export type BareNode = TreeGen<object>;

export type ResponseNode = TreeGen<CollapsedNodeJson>;

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

export type PathToPaperResp = {
	tree: RefDAG;
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

export type OaPaperResp = {
	title: string;
	doi: string;
	abstract: string;
	year: number;
	authors: { name: string; link?: string; institutions: string[] }[];
};
