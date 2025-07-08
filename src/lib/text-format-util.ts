import type { RootType } from './tree-types';

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
					children: { 'topics-false': { semantic: 'specifically' } },
					semantic: 'working on'
				}
			},
			semantic: 'are cited by authors working in'
		},
	}
};
