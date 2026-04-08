import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { BE_URL, COMPLETE_YEAR, REL_TYPES, ROOT_TYPES } from '$lib/constants';
import { pluralize, SEMANTIC_CONF } from '$lib/text-format-util';
import { getExternalUrl, semIdResolver } from '$lib/route-functions';
import { PaperDb } from '$lib/server/db';


export const ssr = true;

const INITIAL_WORKS_N = 20;

export const load: PageServerLoad = async ({ params, url, locals }) => {
	let { rootType, semanticId, conf, spec, treeSpecs } = await semIdResolver(params, url, "");
	const view: tt.View = await fetch(tf.viewBeUrl(BE_URL, conf))
		.then((res) => res.json())
		.then((view) => view)
		.catch(() => error(404, 'Not found'));
	if (view == undefined) {
		error(404, 'Not found');
	}

	const treeResp: tt.TreeResponse = await fetch(tf.treeBeUrl(BE_URL, conf, 1))
		.then((res) => res.json())
		.then((resp) => resp);
	if (treeResp.tree == undefined || treeResp.shallowed == undefined || treeResp.atts == undefined) {
		error(404, 'Not found');
	}
	const { tree, atts, shallowed } = treeResp;

	let svgLinkBase = `/pic/${rootType}/${semanticId}/breakdown.svg`
	let sp = url.searchParams.toString();
	if (sp.length > 0) svgLinkBase += `?${sp}`;
	let svgLink = getExternalUrl(svgLinkBase);

	let paperText = pluralize('paper', view.papers);
	let citeText = pluralize('indexed citation', view.citations);
	let aboutParagraph = getSemanticRels(view, view.name, rootType, paperText, citeText, semanticId);

	let prefixText = SEMANTIC_CONF[rootType]?.start || '';
	let metaDescriptions = `Breaking down the academic impact of ${prefixText.toLowerCase()} ${view.name} - ( ${paperText}, ${citeText} )`;

	// Author-specific data (null/empty defaults for all other entity types)
	let profile: tt.PaperProfileResp | null = null;
	let peersData: tt.EntityPeersResp | null = null;
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

	if (rootType === 'authors') {
		const urlFriendlySemId = tf.urlFriendlify(semanticId);
		const [profileResp, peersResp, worksResp]: [
			tt.PaperProfileResp | null,
			tt.EntityPeersResp | null,
			tt.PaginatedPaperSetResp | null
		] = await Promise.all([
			fetch(`${BE_URL}/paper-profile/${urlFriendlySemId}`)
				.then((r) => r.json())
				.catch(() => null),
			fetch(`${BE_URL}/author-peers/${urlFriendlySemId}`)
				.then((r) => (r.ok ? r.json() : null))
				.catch(() => null),
			fetch(`${BE_URL}/works/authors/${urlFriendlySemId}/0?n=${INITIAL_WORKS_N}`)
				.then((r) => r.json())
				.catch(() => null)
		]);

		profile = profileResp;
		peersData = peersResp;

		if (worksResp) {
			initialPapers = worksResp.resp.papers;
			initialEntityAtts = worksResp.resp.entityAtts;
			initialDiscAuthorNames = worksResp.resp.discAuthorNames;
			initialTotalPapers = worksResp.totalPapers;
			initialWorksSliceEnd = worksResp.sliceStart + worksResp.resp.papers.length;
		}

		if (locals.user) {
			if (locals.user.semanticId) {
				isOwner = locals.user.semanticId === semanticId;
			} else {
				try {
					const orcidResp: tt.SearchResult = await fetch(
						`${BE_URL}/orcid/${locals.user.orcid}`
					).then((r) => r.json());
					isOwner = orcidResp.semanticId === semanticId;
				} catch {
					// ORCID lookup failed — not an owner
				}
			}

			if (isOwner) {
				disownedWids = PaperDb.getDisownedWids(locals.user.orcid);
				claimedDois = PaperDb.getClaimedDois(locals.user.orcid);
				mergedPairs = PaperDb.getMergedPairs(locals.user.orcid);
				authorMergeRequests = PaperDb.getAuthorMergeRequests(locals.user.orcid);
			}
		}
	}

	if (view) {
		return {
			view, conf, treeSpecs, selectionState: spec.selectionState, tree, atts, svgLink,
			shallowed, aboutParagraph, metaDescriptions, paperText, citeText, prefixText,
			profile, peersData,
			initialPapers, initialEntityAtts, initialDiscAuthorNames,
			initialTotalPapers, initialWorksSliceEnd,
			isOwner, disownedWids, claimedDois, mergedPairs, authorMergeRequests,
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
	return (rels: tt.RelatedEntity[]) =>
		prefix + commaAndjoin([...rels.slice(0, 10).map((r) => fun(toDecorated(r)))]);
}

function toDecorated(r: tt.RelatedEntity): DecoratedRelated {
	let bold = `<b>${r.name}</b>`;
	let link = bold;
	if (ROOT_TYPES.includes(r.etype as tt.RootType) && r.semanticId.length > 0) {
		let href = tf.entToLink({ rootType: r.etype as tt.RootType, semanticId: r.semanticId });
		link = `<a class="ali" href="${href}">${r.name}</a>`;
	}
	return {
		score: r.score,
		name: r.name,
		bold,
		link
	};
}

function getSemantifyers(rootName: string, rootType: tt.RootType, paperText: number, citeText: number): [tt.RelTypes, Semantifyer][] {
	if (rootType == 'authors') {
		return [
			[
				'paper-fields',
				semFunMaker(`According to data from OpenAlex, ${rootName} has authored ${paperText} receiving a total of ${citeText} (citations by other indexed papers that have themselves been cited), including `,
					(r) => `${pluralize('paper', r.score)} in ${r.link}`)
			],
			[
				'paper-topics',
				semFunMaker(
					`Recurrent topics in ${rootName}'s work include `,
					(r) => `${r.bold} (${pluralize('paper', r.score)})`
				)
			],
			[
				'paper-topics',
				semFunMaker(
					`${rootName} is often cited by papers focused on `,
					(r) => `${r.name} (${pluralize('paper', r.score)})`
				)
			],
			['collab-nation', semFunMaker(`${rootName} collaborates with scholars based in `, (r) => r.link)],
			['paper-authors', semFunMaker(`${rootName}'s co-authors include `, (r) => r.link)],
			[
				'paper-journals',
				semFunMaker('and has published in prestigious journals such as ', (r) => r.link)
			]
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
					`Papers on ${rootType} are most often about the specific topic of `,
					(r) => r.name
				)
			],
			['paper-fields', semFunMaker('and also cover the fields of ', (r) => r.link)],
			[
				'citing-fields',
				semFunMaker(`Papers citing papers on ${rootType} are usually about `, (r) => r.link)
			],
			[
				'paper-authors',
				semFunMaker(`Some of the most active scholars covering ${rootName} are `, (r) => r.link)
			]
		];
	} else if (rootType == 'hit-papers') {
		return [
			['paper-authors', semFunMaker('Written by ', (r) => r.link)],
			[
				'paper-fields',
				semFunMaker('covering the research area of ', (r) => r.link)
			],
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
		let slug = (view.meta || {}).wikiSlug || '';
		if (slug.length > 0) {
			return `You can learn more about the impact of ${view.name} by visiting their  <a href="https://pantheon.world/profile/person/${slug}" target="_blank" class="ali">Pantheon page</a>.`
		}
	} else if (rootType == 'countries') {
		let oecLink = `https://oec.world/en/profile/country/${semanticId}`
		return `You can explore the trade impact of ${view.name}, by visiting their  <a href="${oecLink}" target="_blank" class="ali">OEC page</a>.`
	} else if (rootType == 'hit-papers') {
		if (!semanticId.startsWith('W')) {
			return `This paper is also available at <a href="https://doi.org/${semanticId}" target="_blank" class="ali">doi.org/${semanticId}</a>.`
		}
		return `This paper is also catalogued at <a href="https://openalex.org/${semanticId}" target="_blank" class="ali">OpenAlex</a>.`
	}
	return ''
}

function getSemanticRels(
	view: tt.View,
	rootName: string,
	rootType: tt.RootType,
	paperText: string,
	citeText: string,
	semanticId: string,
): tt.AboutPara {
	let semantifyers = getSemantifyers(rootName, rootType, paperText, citeText);
	let relationsMap = Object.fromEntries(
		REL_TYPES.map((e) => [e as tt.RelTypes, [] as tt.RelatedEntity[]])
	) as Record<tt.RelTypes, tt.RelatedEntity[]>;
	for (const rel of view.primeRelations) {
		relationsMap[REL_TYPES[rel.relType]].push(rel);
	}
	const out: string[] = [];
	for (const [relK, relSemantifyer] of semantifyers) {
		const result = relSemantifyer(relationsMap[relK]);
		if (result.trim()) out.push(result);
	}

	let postText = sentenceJoiner(out);
	const relFieldLinks = semFunMaker("", (r) => (r.link))(relationsMap['paper-fields']);
	let prefixes: Record<tt.RootType, string> = {
		authors: `${rootName} is a scholar working on ${relFieldLinks}`,
		institutions: `In recent decades, authors affiliated with ${rootName} have published ${paperText}, which have received a total of ${citeText}`,
		countries: `In recent decades scholars affiliated with institutions in ${rootName} have published ${paperText}, which have received a total of ${citeText}`,
		subfields: `${paperText} covering ${rootName} have received a total of ${citeText} since ${COMPLETE_YEAR}`,
		sources: `The ${paperText} published in ${rootName} in the last decades have received a total of ${citeText}`,
		'hit-papers': `This paper, published in ${view.startYear}, received ${citeText}`
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
	let lastN = parts.length - 1;
	if (lastN == 0) return parts[lastN];
	return [parts.slice(0, lastN).join(', '), parts[lastN]].join(' and ');
}

function sentenceJoiner(parts: string[]) {
	const out = [];
	for (let i = 0; i < parts.length - 1; i++) {
		let nextS = parts[i + 1];
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

function getTopRels(view: tt.View) {
	const out = [];
	let id = 0;
	let sub: tt.SubbedRel = { desc: REL_TYPES[id], subs: [] };
	for (const rel of view.primeRelations) {
		if (rel.relType != id) {
			out.push(sub);
			id = rel.relType;
			sub = { desc: REL_TYPES[id], subs: [] };
		}
		sub.subs.push(rel);
	}
	out.push(sub);
	return out;
}
