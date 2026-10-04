<script lang="ts" context="module">
	export type TableCardColumn = { label: string; sorted: boolean };
	export type TableCardRow = {
		rank: string;
		name: string;
		values: string[];
		highlight: boolean;
		pinned: boolean;
	};
</script>

<script lang="ts">
	import { getColorArr } from '$lib/style-util';
	import {
		ACCENT,
		CHAR_W,
		FAINT,
		HAIRLINE,
		INK,
		INNER,
		MONO,
		MUTED,
		SANS,
		clip,
		clipToWidth,
		textWidth
	} from '$lib/utils/cards';

	// A ranking table: the header in small caps over right-aligned numbers, highlighted rows tinted,
	// pinned rows above the ranked ones, the cohort note under the rows when they leave room.
	export let columns: TableCardColumn[];
	export let rows: TableCardRow[];
	export let note: string;

	const PAD = 10;
	const GAP = 28;
	const RANK_GAP = 18;
	const HEAD_SIZE = 13;
	const HEAD_SPACING = 0.8;
	const HEAD_LINE = 16;
	const HEAD_MAX_W = 150;
	// Capitals run wider than the face's mixed-case average.
	const CAPS_ADVANCE = HEAD_SIZE * 0.68 + HEAD_SPACING;
	const NOTE_SIZE = 15;
	const NOTE_H = 30;
	const ROW_MAX = 34;
	const ROW_MIN = 22;
	const TINT = `rgba(${getColorArr(0.4).join(',')}, 0.12)`;

	$: heads = columns.map((c) => wrapCaps(c.label.toUpperCase()));
	$: headH = Math.max(1, ...heads.map((l) => l.length)) * HEAD_LINE + 12;
	$: roomy = (INNER.h - headH - NOTE_H) / rows.length >= ROW_MIN;
	$: rowH = Math.min(ROW_MAX, (INNER.h - headH - (roomy ? NOTE_H : 0)) / rows.length);
	$: nameSize = clamp(rowH * 0.55, 15, 18);
	$: numSize = clamp(rowH * 0.5, 14, 16);
	$: rankR = PAD + Math.max(capsWidth('#'), ...rows.map((r) => monoWidth(r.rank)));
	$: nameX = rankR + RANK_GAP;
	$: valueW = columns.map((_, i) => Math.max(...rows.map((r) => monoWidth(r.values[i]))));
	$: colW = valueW.map((w, i) => Math.max(w, ...heads[i].map(capsWidth)));
	$: nameRoom = INNER.w - PAD - nameX - sum(colW) - GAP * columns.length;
	$: nameNeed = Math.max(...rows.map((r) => textWidth(r.name, nameSize)));
	$: gap = GAP + Math.max(0, nameRoom - nameNeed) / Math.max(1, columns.length);
	$: rights = colW.map(
		(_, i) => INNER.w - PAD - sum(colW.slice(i + 1)) - gap * (colW.length - 1 - i)
	);
	// A name may run under the first column's header, up to its widest value.
	$: nameW = rights[0] - valueW[0] - GAP - nameX;
	$: pinnedCount = rows.filter((r) => r.pinned).length;
	$: laid = rows.map((r, i) => ({
		...r,
		y: headH + i * rowH,
		name: clipToWidth(r.name, nameW, nameSize)
	}));
	$: tableEnd = headH + rows.length * rowH;

	function clamp(v: number, lo: number, hi: number) {
		return Math.min(hi, Math.max(lo, v));
	}

	function sum(xs: number[]) {
		return xs.reduce((a, b) => a + b, 0);
	}

	function capsWidth(text: string) {
		return text.length * CAPS_ADVANCE;
	}

	function monoWidth(text: string) {
		return textWidth(text, numSize, CHAR_W.mono);
	}

	// Words onto at most two lines of HEAD_MAX_W (a longer word gets its own line), the rest
	// clipped into the second.
	function wrapCaps(label: string): string[] {
		const lines: string[] = [];
		for (const word of label.split(' ')) {
			const last = lines.at(-1);
			if (last !== undefined && capsWidth(`${last} ${word}`) <= HEAD_MAX_W)
				lines[lines.length - 1] = `${last} ${word}`;
			else lines.push(word);
		}
		if (lines.length <= 2) return lines;
		const perLine = Math.floor(HEAD_MAX_W / CAPS_ADVANCE);
		return [lines[0], clip(lines.slice(1).join(' '), perLine)];
	}

	function baseline(y: number, size: number) {
		return y + rowH / 2 + size * 0.36;
	}
</script>

<svg viewBox="0 0 {INNER.w} {INNER.h}" xmlns="http://www.w3.org/2000/svg">
	<g font-family={SANS} font-size={HEAD_SIZE} letter-spacing={HEAD_SPACING} fill={MUTED}>
		<text x={rankR} y={headH - 10} text-anchor="end">#</text>
		<text x={nameX} y={headH - 10}>NAME</text>
		{#each heads as lines, i (i)}
			{#each lines as line, j (j)}
				<text
					x={rights[i]}
					y={headH - 10 - (lines.length - 1 - j) * HEAD_LINE}
					text-anchor="end"
					fill={columns[i].sorted ? INK : MUTED}>{line}</text
				>
			{/each}
		{/each}
	</g>
	<line x1={0} x2={INNER.w} y1={headH} y2={headH} stroke={FAINT} stroke-width="1.5" />
	{#each laid as r, i (i)}
		{#if r.highlight}
			<rect x={0} y={r.y} width={INNER.w} height={rowH} fill={TINT} />
		{/if}
		{#if i < rows.length - 1}
			<line
				x1={0}
				x2={INNER.w}
				y1={r.y + rowH}
				y2={r.y + rowH}
				stroke={i === pinnedCount - 1 ? FAINT : HAIRLINE}
				stroke-width={i === pinnedCount - 1 ? 1.5 : 1}
			/>
		{/if}
		<g font-family={MONO} font-size={numSize} text-anchor="end">
			<text x={rankR} y={baseline(r.y, numSize)} fill={MUTED}>{r.rank}</text>
			{#each r.values as v, j (j)}
				<text
					x={rights[j]}
					y={baseline(r.y, numSize)}
					fill={INK}
					font-weight={columns[j].sorted ? 700 : 400}>{v}</text
				>
			{/each}
		</g>
		<text
			x={nameX}
			y={baseline(r.y, nameSize)}
			font-family={SANS}
			font-size={nameSize}
			fill={r.highlight ? ACCENT : INK}>{r.name}</text
		>
	{/each}
	{#if roomy}
		<text x={PAD} y={tableEnd + NOTE_H - 8} font-family={SANS} font-size={NOTE_SIZE} fill={MUTED}
			>{clipToWidth(note, INNER.w - 2 * PAD, NOTE_SIZE)}</text
		>
	{/if}
</svg>
