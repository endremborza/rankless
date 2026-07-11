import { error, redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { BE_URL, COMPLETE_YEAR, REL_TYPES, ROOT_TYPES } from '$lib/constants';
import { pluralize, SEMANTIC_CONF } from '$lib/text-format-util';
import { getExternalUrl, semIdResolver } from '$lib/route-functions';
import { fixViewNames, fixAttNames, fixPeerNames } from '$lib/name-overrides';
import { LedgerDb } from '$lib/server/db';
import { readManifest, EMPTY_MANIFEST } from '$lib/server/manifest';
import { computeEffective } from '$lib/utils/ledger-effective';
import type { LedgerEvent, AppliedManifest } from '$lib/types/ledger';

export const ssr = true;

const INITIAL_WORKS_N = 20;
const PEER_ROOT_TYPES: tt.RootType[] = ['authors', 'institutions', 'countries', 'sources'];

export const load: PageServerLoad = async ({ params, url, locals, fetch: rawFetch, request }) => {
	// Bind the request's abort signal into every backend fetch so a client that
	// disconnects mid-render (bots reading <head> then bailing, nginx->bun upstream
	// timeouts) cancels its in-flight work instead of leaving bun holding the fetched
	// tree + render context — the FE OOM leak. Shadows `fetch` for the whole load.
	const fetch: typeof rawFetch = (input, init) =>
		rawFetch(input, { ...init, signal: request.signal });
	const { rootType, semanticId, conf, spec, treeSpecs } = await semIdResolver(
		params,
		url,
		'',
		fetch
	);
	const view: tt.View | undefined = await fetch(tf.viewBeUrl(BE_URL, conf))
		.then((res) => (res.ok ? res.json() : undefined))
		.catch(() => undefined);
	// An unresolved entity (renamed/mistyped slug) sends the visitor to search rather than a dead
	// 404 — the slug usually reads as the query (e.g. "geoffrey-e-hinton" → "geoffrey e hinton").
	if (view == undefined || view.name == undefined) {
		redirect(307, `/search?q=${encodeURIComponent(semanticId.replace(/-/g, ' '))}`);
	}
	fixViewNames(view);

	const treeResp: tt.TreeResponse = await fetch(tf.treeBeUrl(BE_URL, conf, 1))
		.then((res) => res.json())
		.then((resp) => resp);
	if (treeResp.tree == undefined || treeResp.shallowed == undefined || treeResp.atts == undefined) {
		error(404, 'Not found');
	}
	const { tree, atts, shallowed } = treeResp;
	fixAttNames(atts);

	const cardQuery = url.searchParams.toString();
	const cardSuffix = cardQuery.length > 0 ? `?${cardQuery}` : '';
	const cardBase = `/pic/${rootType}/${semanticId}/breakdown`;
	const svgLink = getExternalUrl(`${cardBase}.svg${cardSuffix}`);
	// Social crawlers don't render SVG OG images, so the share card points at the rasterized PNG.
	const pngLink = getExternalUrl(`${cardBase}.png${cardSuffix}`);

	const paperText = pluralize('paper', view.papers);
	const citeText = pluralize('indexed citation', view.citations);
	const aboutParagraph = getSemanticRels(
		view,
		view.name,
		rootType,
		paperText,
		citeText,
		semanticId
	);

	const prefixText = SEMANTIC_CONF[rootType]?.start || '';
	const metaDescriptions = `Breaking down the academic impact of ${prefixText.toLowerCase()} ${view.name} - ( ${paperText}, ${citeText} )`;

	// Author-specific data (null/empty defaults for all other entity types)
	let profile: tt.PaperProfileResp | null = null;
	let peersPromise: Promise<tt.EntityPeersResp | null> = Promise.resolve(null);
	let ladderPromise: Promise<tt.LadderData | null> = Promise.resolve(null);
	let initialPapers: tt.Paper[] = [];
	let initialEntityAtts: tt.EntityAttsForLinks = {};
	let initialDiscAuthorNames: Record<string, string> = {};
	let initialTotalPapers = 0;
	let initialWorksSliceEnd = 0;
	let isOwner = false;
	let disownedWids: number[] = [];
	let claimedDois: string[] = [];
	let mergedPairs: [number, number][] = [];
	let authorMergeRequests: tt.AuthorMergeRequest[] = [];
	let ledgerEvents: LedgerEvent[] = [];
	let ledgerManifest: AppliedManifest = EMPTY_MANIFEST;

	// Peers are available for these root entity types (each has a precomputed peer set + ladder).
	// The ladder is fetched alongside so the hero header can render standing badges in SSR.
	if (PEER_ROOT_TYPES.includes(rootType)) {
		peersPromise = fetch(`${BE_URL}/peers/${rootType}/${tf.urlFriendlify(semanticId)}`)
			.then((r) => (r.ok ? r.json() : null))
			.catch(() => null);
		ladderPromise = fetch(`${BE_URL}/ladder/${rootType}`)
			.then((r) => (r.ok ? r.json() : null))
			.catch(() => null);
	}

	if (rootType === 'authors') {
		const urlFriendlySemId = tf.urlFriendlify(semanticId);
		const [profileResp, worksResp]: [tt.PaperProfileResp | null, tt.PaginatedPaperSetResp | null] =
			await Promise.all([
				fetch(`${BE_URL}/paper-profile/${urlFriendlySemId}`)
					.then((r) => r.json())
					.catch(() => null),
				fetch(`${BE_URL}/works/authors/${urlFriendlySemId}/0?n=${INITIAL_WORKS_N}&sort=citations`)
					.then((r) => r.json())
					.catch(() => null)
			]);

		profile = profileResp;

		if (worksResp) {
			initialPapers = worksResp.resp.papers;
			initialEntityAtts = worksResp.resp.entityAtts;
			initialDiscAuthorNames = worksResp.resp.discAuthorNames;
			initialTotalPapers = worksResp.totalPapers;
			initialWorksSliceEnd = worksResp.sliceStart + worksResp.resp.papers.length;
		}

		let authorOrcid: string | null = null;
		if (locals.user) {
			if (locals.user.semanticId) {
				isOwner = locals.user.semanticId === semanticId;
				if (isOwner) authorOrcid = locals.user.orcid;
			} else {
				try {
					const orcidResp: tt.SearchResult = await fetch(
						`${BE_URL}/orcid/${locals.user.orcid}`
					).then((r) => r.json());
					isOwner = orcidResp.semanticId === semanticId;
					if (isOwner) authorOrcid = locals.user.orcid;
				} catch {
					// ORCID lookup failed — not an owner
				}
			}
		}
		if (!authorOrcid) {
			try {
				const resolveResp = await fetch(
					`${BE_URL}/resolve/author?semantic_id=${encodeURIComponent(urlFriendlySemId)}`
				).then((r) => (r.ok ? r.json() : null));
				authorOrcid = resolveResp?.orcid ?? null;
			} catch {
				// author ORCID not resolvable
			}
		}
		if (authorOrcid) {
			try {
				const events = LedgerDb.getEventsForOrcid(authorOrcid) as unknown as LedgerEvent[];
				const manifest = readManifest();
				const effective = computeEffective(events, manifest);
				disownedWids = [...effective.disownedWids];
				mergedPairs = effective.mergedPairs;
				if (isOwner) {
					ledgerManifest = manifest;
					ledgerEvents = events;
					claimedDois = events
						.filter(
							(e) =>
								e.kind === 'claim_paper' &&
								e.revoked_at === null &&
								e.payload.kind === 'claim_paper'
						)
						.map((e) => (e.payload.kind === 'claim_paper' ? (e.payload.work.doi ?? '') : ''))
						.filter(Boolean);
					authorMergeRequests = events
						.filter(
							(e) =>
								e.kind === 'merge_authors' &&
								e.revoked_at === null &&
								e.payload.kind === 'merge_authors'
						)
						.map((e) => {
							if (e.payload.kind !== 'merge_authors') return null;
							return {
								other_semantic_id: e.payload.drop.display_snapshot.display_name,
								note: e.payload.note ?? null,
								created_at: e.created_at
							};
						})
						.filter(Boolean) as tt.AuthorMergeRequest[];
				}
			} catch {
				// ledger unavailable — proceed without changes
			}
		}
	}

	const [peersData, ladder] = await Promise.all([peersPromise, ladderPromise]);
	if (peersData) fixPeerNames(peersData);

	if (view) {
		return {
			view,
			conf,
			treeSpecs,
			selectionState: spec.selectionState,
			tree,
			atts,
			svgLink,
			pngLink,
			shallowed,
			aboutParagraph,
			metaDescriptions,
			paperText,
			citeText,
			prefixText,
			profile,
			peersData,
			ladder,
			initialPapers,
			initialEntityAtts,
			initialDiscAuthorNames,
			initialTotalPapers,
			initialWorksSliceEnd,
			isOwner,
			disownedWids,
			claimedDois,
			mergedPairs,
			authorMergeRequests,
			ledgerEvents,
			ledgerManifest
		};
	}

	error(404, 'Not found');
};

type Semantifyer = (rels: tt.RelatedEntity[]) => string;

type DecoratedRelated = {
	score: number;
	name: string;
	link: string;
	bold: string;
};

function semFunMaker(prefix: string, fun: (r: DecoratedRelated) => string) {
	return (rels: tt.RelatedEntity[]) => {
		const items = rels.slice(0, 10);
		if (items.length === 0) return '';
		return prefix + commaAndjoin(items.map((r) => fun(toDecorated(r))));
	};
}

function toDecorated(r: tt.RelatedEntity): DecoratedRelated {
	const bold = `<b>${r.name}</b>`;
	let link = bold;
	if (ROOT_TYPES.includes(r.etype as tt.RootType) && r.semanticId.length > 0) {
		const href = tf.entToLink({ rootType: r.etype as tt.RootType, semanticId: r.semanticId });
		link = `<a class="ali" href="${href}">${r.name}</a>`;
	}
	return {
		score: r.score,
		name: r.name,
		bold,
		link
	};
}

function getSemantifyers(rootName: string, rootType: tt.RootType): [tt.RelTypes, Semantifyer][] {
	if (rootType == 'authors') {
		return [
			[
				'paper-topics',
				semFunMaker(
					`Recurring topics across this work include `,
					(r) => `${r.bold} (${pluralize('paper', r.score)})`
				)
			],
			[
				'citing-fields',
				semFunMaker(
					`The work is most often cited by research in `,
					(r) => `${r.name} (${pluralize('citation', r.score)})`
				)
			],
			[
				'collab-nation',
				semFunMaker(`${rootName} has collaborated with scholars based in `, (r) => r.link)
			],
			['paper-authors', semFunMaker(`Frequent co-authors include `, (r) => r.link)],
			['paper-journals', semFunMaker(`Their work appears in journals such as `, (r) => r.link)]
		];
	} else if (rootType == 'institutions') {
		return [
			[
				'paper-fields',
				semFunMaker(
					'Scholars at this organization have produced ',
					(r) => `${pluralize('paper', r.score)} in ${r.name}`
				)
			],
			[
				'paper-topics',
				semFunMaker('on the topics of ', (r) => `${r.name} (${pluralize('paper', r.score)})`)
			],
			[
				'citing-fields',
				semFunMaker(
					`Their work is cited by papers focused on `,
					(r) => `${r.name} (${pluralize('citation', r.score)})`
				)
			],
			[
				'collab-nation',
				semFunMaker(`Authors at ${rootName} collaborate with scholars in `, (r) => r.link)
			],
			[
				'paper-journals',
				semFunMaker('and have published in prestigious journals including ', (r) => r.link)
			],
			[
				'paper-authors',
				semFunMaker(`Some of ${rootName}'s most productive authors include `, (r) => r.link)
			]
		];
	} else if (rootType == 'countries') {
		return [
			[
				'paper-fields',
				semFunMaker(
					`Scholars in ${rootName} publish mostly in `,
					(r) => `${r.name} (${pluralize('paper', r.score)})`
				)
			],
			[
				'citing-fields',
				semFunMaker(
					'and are cited by scholars working on ',
					(r) => `${r.name} (${pluralize('citation', r.score)})`
				)
			],
			[
				'collab-nation',
				semFunMaker(`Scholars in ${rootName} collaborate with scholars from `, (r) => r.link)
			],
			[
				'paper-journals',
				semFunMaker(
					`Scholars in ${rootName} have published in prestigous journals including `,
					(r) => r.link
				)
			]
		];
	} else if (rootType == 'sources') {
		return [
			[
				'paper-fields',
				semFunMaker(
					`Papers published in ${rootName} usually cover `,
					(r) => `${r.link} (${pluralize('paper', r.score)})`
				)
			],
			[
				'paper-topics',
				semFunMaker(
					'specifically the topics of ',
					(r) => `${r.name} (${pluralize('paper', r.score)})`
				)
			],
			[
				'paper-authors',
				semFunMaker(`The most active scholars publishing in ${rootName} are `, (r) => r.link)
			]
		];
	} else if (rootType == 'subfields') {
		return [
			[
				'paper-topics',
				semFunMaker(
					`Papers on ${rootName} are most often about the specific topic of `,
					(r) => r.name
				)
			],
			['paper-fields', semFunMaker('and also cover the fields of ', (r) => r.link)],
			[
				'citing-fields',
				semFunMaker(`Papers citing work on ${rootName} are usually about `, (r) => r.link)
			],
			[
				'paper-authors',
				semFunMaker(`Some of the most active scholars covering ${rootName} are `, (r) => r.link)
			]
		];
	} else if (rootType == 'hit-papers') {
		return [
			['paper-authors', semFunMaker('Written by ', (r) => r.link)],
			['paper-fields', semFunMaker('covering the research area of ', (r) => r.link)],
			[
				'citing-fields',
				semFunMaker(
					'It is primarily cited by scholars working on ',
					(r) => `${r.link} (${pluralize('citation', r.score)})`
				)
			],
			['paper-journals', semFunMaker('Published in ', (r) => r.link)]
		];
	}

	return [];
}

function getFootText(rootType: tt.RootType, view: tt.View, semanticId: string) {
	if (rootType == 'authors') {
		const slug = (view.meta || {}).wikiSlug || '';
		if (slug.length > 0) {
			return `You can learn more about the impact of ${view.name} by visiting their  <a href="https://pantheon.world/profile/person/${slug}" target="_blank" class="ali">Pantheon page</a>.`;
		}
	} else if (rootType == 'countries') {
		const oecLink = `https://oec.world/en/profile/country/${semanticId}`;
		return `You can explore the trade impact of ${view.name}, by visiting their  <a href="${oecLink}" target="_blank" class="ali">OEC page</a>.`;
	} else if (rootType == 'hit-papers') {
		if (!semanticId.startsWith('W')) {
			return `This paper is also available at <a href="https://doi.org/${semanticId}" target="_blank" class="ali">doi.org/${semanticId}</a>.`;
		}
		return `This paper is also catalogued at <a href="https://openalex.org/${semanticId}" target="_blank" class="ali">OpenAlex</a>.`;
	}
	return '';
}

function getSemanticRels(
	view: tt.View,
	rootName: string,
	rootType: tt.RootType,
	paperText: string,
	citeText: string,
	semanticId: string
): tt.AboutPara {
	const semantifyers = getSemantifyers(rootName, rootType);
	const relationsMap = Object.fromEntries(
		REL_TYPES.map((e) => [e, view.relations[e] ?? []])
	) as Record<tt.RelTypes, tt.RelatedEntity[]>;
	const out: string[] = [];
	for (const [relK, relSemantifyer] of semantifyers) {
		const result = relSemantifyer(relationsMap[relK]);
		if (result.trim()) out.push(result);
	}

	const postText = sentenceJoiner(out);
	const relFieldLinks = semFunMaker('', (r) => r.link)(relationsMap['paper-fields']);
	const authorPrefix = relFieldLinks
		? `${rootName} is a scholar working on ${relFieldLinks}, having authored ${paperText} that have together received ${citeText}`
		: `${rootName} has authored ${paperText} that have together received ${citeText} `;
	const prefixes: Record<tt.RootType, string> = {
		authors: authorPrefix,
		institutions: `In recent decades, authors affiliated with ${rootName} have published ${paperText}, which have received a total of ${citeText} `,
		countries: `In recent decades scholars affiliated with institutions in ${rootName} have published ${paperText}, which have received a total of ${citeText} `,
		subfields: `${paperText} covering ${rootName} have received a total of ${citeText} since ${COMPLETE_YEAR} `,
		sources: `The ${paperText} published in ${rootName} in the last decades have received a total of ${citeText} `,
		'hit-papers': `This paper, published in ${view.startYear}, received ${citeText} `
	};
	return {
		prefix: prefixes[rootType],
		postText,
		topRels: getTopRels(view),
		footText: getFootText(rootType, view, semanticId)
	};
}

function commaAndjoin(parts: string[]) {
	if (parts.length === 0) return '';
	const lastN = parts.length - 1;
	if (lastN == 0) return parts[lastN];
	return [parts.slice(0, lastN).join(', '), parts[lastN]].join(' and ');
}

function sentenceJoiner(parts: string[]) {
	const out = [];
	for (let i = 0; i < parts.length - 1; i++) {
		const nextS = parts[i + 1];
		if (nextS.toLowerCase()[0] == nextS[0]) {
			out.push(parts[i]);
		} else {
			out.push(parts[i] + '.');
		}
	}
	if (parts.length > 0) {
		out.push(parts[parts.length - 1] + '.');
	}
	return out.join(' ');
}

function getTopRels(view: tt.View): tt.SubbedRel[] {
	return REL_TYPES.map((rt) => ({ desc: rt, subs: view.relations[rt] ?? [] })).filter(
		(sub) => sub.subs.length > 0
	);
}
