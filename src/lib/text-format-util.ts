import type { RootType } from './tree-types';

export class TypeWriterWordChanger {
	speed: number;
	stopAtEnd: number;
	texts: string[];
	wordInd: number;
	text: string;
	direction: number;
	letterInd: number;
	runner: number;


	constructor(texts: string[]) {

		this.speed = 80;
		this.stopAtEnd = 480;
		this.texts = texts;
		this.wordInd = 0;
		this.text = texts[this.wordInd];

		this.letterInd = Math.floor(this.text.length / 2);
		this.direction = +1;
		this.runner = 0
	}

	changeText() {
		if (this.wordInd == this.texts.length) {
			this.wordInd = 0;
		}
		let word = this.texts[this.wordInd];
		this.text = word.slice(0, this.letterInd);
		if (this.letterInd == word.length) {
			clearInterval(this.runner);
			setTimeout(() => {
				this.runner = setInterval(this.changeText, this.speed);
			}, this.stopAtEnd);
		}
		this.letterInd += this.direction;
		if (this.letterInd == word.length) {
			this.direction = -1;
		}
		if (this.letterInd == 0) {
			this.direction = 1;
			this.wordInd = this.wordInd + 1;
		}
	}


}

export function isAsciiOnly(str: string) {
	return /^[\x01-\x7F]+$/.test(str);
}

export function pluralize(word: string, num: number, maxFix = 2) {
	if (num == 1) {
		return `1 ${word}`;
	}
	return `${formatNumber(num, maxFix)} ${word}s`;
}

export function singularize(word: string) {
	return SING_MAP[word] || word.substring(0, word.length - 1);
}

export function formatNumber(n: number, maxFix: number = 2) {
	if (n == 0) {
		return "0"
	} else if (n > 1e6) {
		return `${(n / 1e6).toFixed(Math.min(1, maxFix))}M`;
	} else if (n > 1e3) {
		return `${(n / 1e3).toFixed(Math.min(1, maxFix))}k`;
	} else if (n < 1) {
		return n.toFixed(Math.min(2, maxFix));
	} else if (n < 10) {
		let round = n % 1 == 0 ? 0 : maxFix;
		return n.toFixed(round);
	} else {
		return n.toFixed(0);
	}
}

export function getStylesForWords(
	words: string[],
	width: number,
	height: number,
	heightMultiplier: number,
	widthMultiplier: number,
	baseFontSize: number,
	horizontalAlign: 'left' | 'center' | 'right',
	bottomAligned: boolean,
	allowRotation: boolean
) {
	const horizontal = formatTextToLinesOneWay(
		words,
		width,
		height,
		heightMultiplier,
		widthMultiplier
	);
	let rotate = false;
	let { lines, fontSize } = horizontal;
	if (allowRotation) {
		const vertical = formatTextToLinesOneWay(
			words,
			height,
			width,
			heightMultiplier,
			widthMultiplier
		);
		if (horizontal.fontSize < vertical.fontSize) {
			rotate = true;
			lines = vertical.lines;
			fontSize = vertical.fontSize;
		}
	}

	const translates = [];
	const scale = fontSize / baseFontSize;
	const nLines = lines.length;
	let bottomPad = 0;
	if (!bottomAligned) {
		bottomPad +=
			(height / scale - (nLines + (nLines - 1) * (heightMultiplier - 1)) * baseFontSize) / 2;
	}

	const totalMult = widthMultiplier * baseFontSize;
	let baseGetters = {
		center: (words: string[]) => (-lineLen(words) * totalMult) / 2,
		left: () => 0,
		right: (words: string[]) => -lineLen(words) * totalMult
	};
	const getLineBaseX = baseGetters[horizontalAlign];

	for (const [lineInd, line] of lines.entries()) {
		const y = (lineInd - nLines + 1) * heightMultiplier * baseFontSize - bottomPad;
		const lineBaseX = getLineBaseX(line.words);
		let wordStartInd = 0;
		for (const word of line.words) {
			const x = lineBaseX + wordStartInd * totalMult;
			translates.push(`translate(${x}px, ${y}px)`);
			wordStartInd += word.length + 1;
		}
	}

	return { translates, scale, rotate };
}

export function semantify(s: string, rootType: RootType, bds: string[], depth: number) {
	let map = SEM_MAP[rootType] as any;
	for (let i = 0; i < depth; i++) {
		if (map == undefined) {
			return s;
		}
		map = map[bds[i]]?.children;
	}
	if (map == undefined) {
		return s;
	}
	return map[s]?.semantic || s;
}

export function eTypeFromBdDesc(bdDesc: string): RootType {
	return bdDesc.split('-')[0] as RootType
}

export function semOptioned(semId: string, bdDesc: string) {
	let suffix = singularize(eTypeFromBdDesc(bdDesc));
	return `${semId} <${suffix}>`;
}

export function prettifyRoot(rt: RootType): string {
	if (rt == 'sources') return 'journals';
	if (rt == 'subfields') return 'fields';
	return rt;
}

export function getSpecDesc(rate: number) {
	let desc = 'Average';
	if (rate > SPEC_BPS[2]) {
		desc = 'Very High';
	} else if (rate > SPEC_BPS[1]) {
		desc = 'High';
	} else if (rate < SPEC_BPS[0]) {
		desc = 'Low';
	}
	return desc;
}

function formatTextToLinesOneWay(
	words: string[],
	width: number,
	height: number,
	heightMultiplier: number,
	widthMultiplier: number
) {
	let numOfLines = 1;
	const totalLength = lineLen(words);
	let lines = [{ words, length: totalLength }];
	let maxLineLen,
		widthBasedFontSize,
		heightBasedFontSize,
		fontSize: number = 0;
	for (const _ of Array(7)) {
		maxLineLen = lines.reduce((a, b) => Math.max(a, b.length), -Infinity);
		widthBasedFontSize = width / (maxLineLen * widthMultiplier);
		heightBasedFontSize = getDimBasedSize(height, heightMultiplier, numOfLines);
		fontSize = Math.min(widthBasedFontSize, heightBasedFontSize);
		if (
			lines.length == words.length ||
			fontSize >= getDimBasedSize(height, heightMultiplier, numOfLines + 1)
		) {
			return { lines, fontSize };
		}
		lines = splitToLines(words, totalLength, numOfLines + 1);
		if (numOfLines == lines.length) {
			break;
		}
		numOfLines = lines.length;
	}
	return { lines, fontSize };
}

function splitToLines(words: string[], stringLength: number, numOfLines: number) {
	const lines = [];
	let line = [];
	let lineLen = 0;
	const maxPossLineLen = (stringLength / numOfLines) * 1.25;
	for (const word of words) {
		// console.log("increasing at", word, lineLen, word.length)
		lineLen += word.length + 1;

		if (lineLen > maxPossLineLen && line.length > 0) {
			// console.log("pushing", line, lineLen)
			lines.push({ words: line, length: lineLen - word.length - 2 });
			line = [];
			lineLen = word.length + 1;
		}
		line.push(word);
	}
	if (line.length > 0) {
		lines.push({ words: line, length: lineLen - 1 });
	}
	return lines;
}

function getDimBasedSize(dimSize: number, dimMultiplier: number, numOfLines: number) {
	return dimSize / (1 + (numOfLines - 1) * dimMultiplier);
}

function lineLen(words: string[]) {
	return words.reduce((x, y) => x + y.length + 1, 0) - 1;
}

function productionSemantics(rootType: RootType, rootName: string) {
	let prefix = 'papers'
	if (rootType == 'hit-papers') {
		prefix = ''
	}
	return {
		authors: `${prefix} produced by ${rootName}`,
		countries: `${prefix} produced by authors working at institutions in ${rootName}`,
		institutions: `${prefix} affiliated with ${rootName} at the time of their publication`,
		sources: `${prefix} published in ${rootName}`,
		'hit-papers': `${prefix} ${rootName}`,
		subfields: `${prefix} covering ${rootName}`,
	}[rootType]


}

export function getNetworkText(rootType: RootType, rootName: string, isSpec: boolean, sourceSide: boolean) {
	let midNodeExp = 'that tend to cite the'
	let midPrefix = 'impact of';
	if (sourceSide) {
		midNodeExp = 'of impactful'
		midPrefix = 'distribution of'
	}
	let lines = [
		`This network shows the ${midPrefix} ${productionSemantics(rootType, rootName)}.`,
		'Nodes represent research fields, and links connect fields that are likely to share authors.',
		`Colored nodes show fields ${midNodeExp} ${productionSemantics(rootType, rootName)}.`
	];
	if (rootType == 'authors') {
		lines.push(`The network helps show where ${rootName} may publish in the future.`)
	}
	if (rootType == 'countries') {
		lines.push(`The network helps show where authors in ${rootName} may publish in the future.`)
	}
	if (sourceSide)
		lines.push('Since papers are assigned to multiple fields, the same paper can appear as cited in multiple nodes.');
	return lines.join(' ')
}

export function getMapText(rootType: RootType, rootName: string, isSpec: boolean, sourceSide: boolean) {
	let specExplIn = sourceSide ? "country's share of papers is larger" : `country cites ${rootName} more`
	let specExpl = `(numbers larger than one mean the ${specExplIn} than expected)`
	let midPrefix = ''
	if (!isSpec && sourceSide) {
		midPrefix = 'It shows the number of citations received by papers published by authors working in each country. '
	} else if (isSpec && !sourceSide) {
		midPrefix = ''
	} else if (!isSpec && !sourceSide) {
		midPrefix = 'It shows the number of citations coming from papers published by authors working in each country. '
	}
	let [geoNoun, subject] = sourceSide ? ['distribution', 'papers'] : ['impact', 'citations']
	let geoPrefix = `This map shows the geographic ${geoNoun} of `
	let specPref = isSpec ? 'This is a graph of specialization, which compares' : 'You can also color the map by specialization and compare'
	let rootPref = rootSemanticPrefix(rootType, sourceSide)
	let fullSpecSuffix = ` ${midPrefix}${specPref} the number of ${rootPref} ${rootName} with the expected number of ${subject} based on a country's size and research output ${specExpl}.`

	return geoPrefix + {
		authors: `${rootName}'s research.`,
		countries: `research produced by institutions in ${rootName}.`,
		institutions: `research produced by authors working at ${rootName}.`,
		sources: `research published in ${rootName}.`,
		subfields: `research in ${rootName}.`,
		'hit-papers': `${rootName}.`,
	}[rootType] + fullSpecSuffix
}

function rootSemanticPrefix(rootType: RootType, sourceSide: boolean) {
	let citePref = 'citations received by'
	if (sourceSide) {
		return {
			authors: 'papers authored by',
			countries: 'papers written in collaboration with authors working in',
			institutions: 'papers written in collaboration with authors working at',
			sources: 'papers published in',
			'hit-papers': 'the paper',
			subfields: 'papers about',
		}[rootType]
	} else {
		return citePref + {
			authors: '',
			countries: ' papers from institutions in',
			institutions: ' papers produced at',
			sources: ' papers published in',
			'hit-papers': '',
			subfields: ' papers about',
		}[rootType]
	}

}

export const SEMANTIC_CONF = {
	authors: {
		prefix: '👤',
		start: 'Papers by'
	},
	institutions: {
		prefix: '🏛',
		start: 'Scholars at'
	},
	sources: {
		prefix: '📖',
		start: 'Papers in'
	},
	countries: {
		prefix: '🌍',
		start: 'Scholars in'
	},
	subfields: {
		prefix: '💡',
		start: 'Papers covering'
	},
	'hit-papers': {
		prefix: '📃',
		start: 'The Paper'
	}
};

export const SPEC_BPS = [0.75, 1.2, 2.5];
const SING_MAP: Record<string, string> = { countries: 'country' };
const CO_FAL = 'are cited by authors working in';
const SPEC = 'specifically';

const SEM_MAP = {
	authors: {
		'subfields-true': {
			children: {
				'works-true': {
					children: {
						'countries-false': {
							children: { 'institutions-false': { semantic: 'at' } },
							semantic: CO_FAL
						}
					},
					semantic: 'specifically'
				},
				'countries-false': {
					children: {
						'institutions-false': {
							children: { 'subfields-false': { semantic: 'working on' } },
							semantic: 'at'
						}
					},
					semantic: CO_FAL
				},
				'subfields-false': {
					children: { 'topics-false': { semantic: 'specifically' } },
					semantic: 'are cited by papers on'
				}
			},
			semantic: 'about'
		},
		'countries-false': {
			children: {
				'subfields-false': {
					children: { 'topics-false': { semantic: 'specifically' } },
					semantic: 'working on'
				},
				'institutions-false': {
					children: {
						'subfields-false': {
							children: { 'topics-false': { semantic: 'specifically' } },
							semantic: 'working on'
						}
					},
					semantic: 'at'
				}
			},
			semantic: CO_FAL
		},
		'sources-true': {
			children: {
				'works-true': {
					children: {
						'countries-false': {
							children: { 'institutions-false': { semantic: 'at' } },
							semantic: CO_FAL
						}
					},
					semantic: SPEC
				},
				'subfields-true': {
					children: { 'countries-false': { semantic: CO_FAL } },
					semantic: 'about'
				}
			},
			semantic: 'published in'
		},
		"authors-true": {
			children: {
				"works-true": { children: { "subfields-false": { semantic: "are cited by papers covering" } }, semantic: SPEC },
				"countries-false": { "children": { "institutions-false": { "semantic": "specifically at" } }, "semantic": "are cited by authors working in" }
			},
			semantic: "co-authored with"
		}
	},
	institutions: {
		'subfields-true': {
			children: {
				'subfields-false': {
					children: { 'topics-false': { semantic: ' in particular' } },
					semantic: 'are cited by authors working on'
				},
				'countries-false': {
					children: {
						'institutions-false': {
							children: {
								'subfields-false': { semantic: 'working on' },
								'sources-false': { semantic: 'published in' }
							},
							semantic: 'working at'
						}
					},
					semantic: 'are cited by authors working in'
				}
			},
			semantic: 'working on'
		},
		'subfields-false': {
			children: {
				'sources-false': {
					children: { 'topics-false': { semantic: 'covering' } },
					semantic: 'published in'
				}
			},
			semantic: 'are cited by papers on'
		},
		'authors-true': {
			children: {
				'countries-false': {
					children: { 'institutions-false': { semantic: 'working at' } },
					semantic: 'are cited by authors working in'
				}
			},
			semantic: 'specifically'
		},
		'sources-false': {
			children: {
				'countries-false': {
					children: { 'subfields-false': { semantic: 'covering' } },
					semantic: 'written by authors in'
				}
			},
			semantic: 'are cited by papers published in'
		},
		'qs-true': {
			children: {
				'sources-true': {
					children: {
						'subfields-false': {
							children: { 'countries-false': { semantic: 'working in' } },
							semantic: 'get cited by authors covering'
						}
					},
					semantic: 'specifically in'
				}
			},
			semantic: 'publish in journals categorized as'
		},
		'countries-false': {
			children: {
				'institutions-false': {
					children: {
						'subfields-false': {
							children: { 'topics-false': { semantic: 'specifically' } },
							semantic: 'working on'
						}
					},
					semantic: 'at'
				}
			},
			semantic: 'are cited by authors working in'
		},
		'countries-true': {
			children: {
				'subfields-true': {
					children: { 'institutions-true': { semantic: 'working at' } },
					semantic: 'working on'
				}
			},
			semantic: 'collaborate with authors working in'
		}
	},
	sources: {
		'subfields-true': {
			children: {
				'countries-false': {
					children: {
						'institutions-false': {
							children: { 'sources-false': { semantic: 'who published in' } },
							semantic: 'at'
						}
					},
					semantic: 'are cited by authors working in'
				}
			},
			semantic: 'covering'
		},
		'countries-true': {
			children: {
				'institutions-true': {
					children: { 'subfields-true': { semantic: 'on' } },
					semantic: 'at'
				}
			},
			semantic: 'are written by authors working in'
		},
		'sources-false': {
			children: {
				'countries-false': {
					children: { 'subfields-false': { semantic: 'working on' } },
					semantic: 'written by authors working in'
				}
			},
			semantic: 'are cited by papers published in'
		}
	},
	countries: {
		'institutions-true': {
			children: {
				'subfields-true': {
					children: {
						'countries-false': {
							children: { 'institutions-false': { semantic: 'at' } },
							semantic: 'are cited by authors working in'
						}
					},
					semantic: 'working on'
				},
				'sources-true': {
					children: {
						'subfields-true': {
							children: { 'countries-false': { semantic: CO_FAL } },
							semantic: 'writing about'
						}
					},
					semantic: 'publishing in'
				}
			},
			semantic: 'working at'
		},
		'countries-true': {
			children: {
				'institutions-true': {
					children: { 'subfields-true': { semantic: 'writing about' } },
					semantic: 'at'
				}
			},
			semantic: 'collaborate with authors in'
		},
		'countries-false': {
			children: {
				'subfields-false': {
					children: { 'institutions-false': { semantic: 'at' } },
					semantic: 'working on'
				}
			},
			semantic: 'are cited by authors working in'
		}
	},
	subfields: {
		'topics-true': {
			children: {
				'countries-true': {
					children: { 'institutions-true': { semantic: 'at' } },
					semantic: 'written by authors in'
				}
			},
			semantic: SPEC
		},
		'sources-true': {
			children: {
				'countries-true': {
					children: { 'institutions-true': { semantic: 'at' } },
					semantic: 'by authors working in'
				}
			},
			semantic: 'are published in'
		},
		'countries-false': {
			children: {
				'subfields-false': {
					children: { 'topics-false': { semantic: SPEC } },
					semantic: 'working on'
				}
			},
			semantic: 'are cited by authors working in'
		},
	},
	'hit-papers': {
		'subfields-false': {
			children: {
				'sources-false': {
					children: { 'topics-false': { semantic: 'covering' } },
					semantic: 'published in'
				}
			},
			semantic: 'is cited by papers on'
		},
		'countries-false': {
			children: {
				'subfields-false': {
					children: { 'topics-false': { semantic: SPEC } },
					semantic: 'working on'
				}
			},
			semantic: 'is cited by authors working in'
		},
	}
};
