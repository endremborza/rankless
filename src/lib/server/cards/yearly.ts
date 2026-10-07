import { error } from '@sveltejs/kit';
import { METHODOLOGY } from '$lib/wire/rankless_server/responses';
import { listPhrase } from '$lib/text-format-util';
import { seriesYears } from '$lib/utils/year-ticks';
import YearlyCard from '$lib/components/cards/YearlyCard.svelte';
import { flagParam, idsParam, intParam, type CardKind } from './kind';

// The entity's last decade: citations received per year (bars up) and papers published per year
// (bars down, off for a hit paper or with `papers=0`), narrowed to `from`–`to`, with the `hl`
// years highlighted.
export const yearly: CardKind = {
	component: YearlyCard,
	async load({ rootType, params, view }) {
		if (!view) error(404, 'no such card');
		const last = METHODOLOGY.yearlyCounts[1];
		const allYears = seriesYears(view.yearlyCites.length, last);
		const first = allYears[0];
		const from = intParam(params, 'from', first, first, last);
		const to = intParam(params, 'to', last, from, last);
		const hl = [...new Set(idsParam(params, 'hl', allYears.length).map(Number))];
		if (hl.some((y) => !Number.isInteger(y) || y < from || y > to)) error(404, 'bad hl');
		const showPapers = flagParam(params, 'papers', true) && rootType !== 'hit-papers';
		const inWindow = (series: number[]) => series.slice(from - first, to - first + 1);
		return {
			props: {
				years: seriesYears(to - from + 1, to),
				cites: inWindow(view.yearlyCites),
				papers: showPapers ? inWindow(view.yearlyPapers) : null,
				hl
			},
			caption: yearlyCaption(from, to, showPapers, hl)
		};
	}
};

function yearlyCaption(from: number, to: number, showPapers: boolean, hl: number[]): string {
	const series = showPapers
		? 'Citations received per year, and papers published'
		: 'Citations received per year';
	const years = [...hl].sort((a, b) => a - b).map(String);
	const marked = hl.length ? `, ${listPhrase(years, 'and')} highlighted` : '';
	const span = from === to ? `${from}` : `${from}–${to}`;
	return `${series}, ${span}${marked}`;
}
