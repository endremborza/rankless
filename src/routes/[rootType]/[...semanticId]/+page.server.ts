import { error, redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import * as lf from '$lib/loading-functions';
import oldCountrySem from '$lib/assets/data/old-country-semantic-id-map.json';
import alpha2CC from '$lib/assets/data/country-alpha-2-to-3.json';
import { BE_URL, COMPLETE_YEAR, ROOT_TYPES } from '$lib/constants';
import { pluralize, SEMANTIC_CONF } from '$lib/text-format-util';
import { getExternalUrl } from '$lib/route-functions';


export const ssr = true;

export const load: PageServerLoad = async ({ params, url }) => {
	let rootType: tt.RootType;
	if (ROOT_TYPES.includes(params.rootType as tt.RootType)) {
		rootType = params.rootType as tt.RootType;
	} else {
		error(404, 'Not found');
	}
	let semanticId: string = params.semanticId;

	const treeSpecs = await lf.loadSpecs();
	let spec: tt.ShareSpec = tf.parseLinkWithParams(url.searchParams, rootType, treeSpecs);
	let conf: tt.FullTreeConfig = { semanticId, year: spec.year, treeId: spec.treeId, rootType, wide: false };
	let newSemId: string | undefined = semanticId.toLowerCase();
	if (rootType == 'countries') {
		if (semanticId.length == 2) {
			newSemId = alpha2CC[semanticId.toUpperCase()] || newSemId;
		} else if (semanticId.length != 3) {
			newSemId = oldCountrySem[semanticId.toLowerCase()];
		}
	}
	if (newSemId == undefined) {
		error(404, 'Not found');
	}
	if (semanticId != newSemId) {
		let linkBase = tf.entToLink({ rootType, semanticId: newSemId });
		let link = tf.decorBaseLink(linkBase, conf, spec.selectionState)
		redirect(301, link);
	}

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
	let aboutParagraph = getSemanticRels(view, view.name, rootType, paperText, citeText);

	let prefixText = SEMANTIC_CONF[rootType]?.start || '';
	let metaDescriptions = `Breaking down the academic impact of ${prefixText.toLowerCase()} ${view.name} - ( ${paperText}, ${citeText} )`;

	if (view) {
		return { view, conf, treeSpecs, selectionState: spec.selectionState, tree, atts, svgLink, shallowed, aboutParagraph, metaDescriptions, paperText, citeText, prefixText };
	}

	error(404, 'Not found');
};


const REL_TYPES: RelTypes[] = [
	'paper-fields',
	'citing-fields',
	'paper-topics',
	'collab-nation',
	'paper-journals',
	'paper-authors'
];


type RelTypes =
	| 'paper-fields'
	| 'citing-fields'
	| 'paper-topics'
	| 'collab-nation'
	| 'paper-journals'
	| 'paper-authors';

type Semantifyer = (rels: tt.RelatedEntity[]) => string;

type DecoratedRelated = {
	score: number;
	name: string;
	link: string;
	bold: string;
};




function semFunMaker(prefix: string, fun: (r: DecoratedRelated) => string) {
	return (rels: tt.RelatedEntity[]) =>
		prefix + commaAndjoin([...rels.map((r) => fun(toDecorated(r)))]);
}


function toDecorated(r: tt.RelatedEntity): DecoratedRelated {
	let bold = `<b>${r.name}</b>`;
	let link = bold;
	if (ROOT_TYPES.includes(r.etype as tt.RootType)) {
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

function getSemantifyers(rootName: string, rootType: tt.RootType): [RelTypes, Semantifyer][] {
	if (rootType == 'authors') {
		return [
			[
				'paper-fields',
				semFunMaker('This includes ', (r) => `${pluralize('paper', r.score)} in ${r.link}`)
			],
			[
				'paper-topics',
				semFunMaker(
					'The topics of these papers are ',
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
			['collab-nation', semFunMaker('and collaborates with scholars based in ', (r) => r.link)],
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
	}

	return [];
}

function extendPostText(rootType: tt.RootType, view: tt.View, postText: string) {
	if (rootType == 'authors') {
		let slug = (view.meta || {}).wikiSlug || '';
		if (slug.length > 0) {
			return postText + `<br/> You can learn more about the impact of ${view.name} by visiting their  <a href="https://pantheon.world/profile/person/${slug}" target="_blank">Pantheon page</a>`
		}
	}
	return postText
}

function getSemanticRels(
	view: tt.View,
	rootName: string,
	rootType: tt.RootType,
	paperText: string,
	citeText: string
): tt.AboutPara {
	let semantifyers = getSemantifyers(rootName, rootType);
	let relationsMap = Object.fromEntries(
		REL_TYPES.map((e) => [e as RelTypes, [] as tt.RelatedEntity[]])
	) as Record<RelTypes, tt.RelatedEntity[]>;
	for (const rel of view.primeRelations) {
		relationsMap[REL_TYPES[rel.relType]].push(rel);
	}
	const out: string[] = [];
	for (const [relK, relSemantifyer] of semantifyers) {
		out.push(relSemantifyer(relationsMap[relK]));
	}

	let postText = sentenceJoiner(out);
	let prefixes: Record<tt.RootType, string> = {
		authors: `${rootName} has authored ${paperText} that have received a total of ${citeText}`,
		institutions: `In recent decades, authors affiliated with ${rootName} have published ${paperText}, which have received a total of ${citeText}`,
		countries: `In recent decades scholars affiliated with institutions in ${rootName} have published ${paperText}, which have received a total of ${citeText}`,
		subfields: `${paperText} covering ${rootName} have received a total of ${citeText} since ${COMPLETE_YEAR}`,
		sources: `The ${paperText} published in ${rootName} in the last decades have received a total of ${citeText}`,
		'hit-papers': `The paper ${rootName} received a total of ${citeText}`
	};
	return {
		prefix: prefixes[rootType],
		postText: extendPostText(rootType, view, postText),
		topRels: getTopRels(view)
	};
}

function commaAndjoin(parts: string[]) {
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

