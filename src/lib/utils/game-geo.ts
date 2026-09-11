// Client-side rules of the geography quiz: the question each card kind asks,
// the daily recipe and survival lives, the question timer, the 50:50 lifeline
// and half-point scoring, the share grid and the personal stats.
// Shared game plumbing is in utils/game.ts, types in types/game-geo.ts.

import { ccFlag, ccName, fnv1a, shareMessage, shuffle } from './game';
import type { CardKind, DailyRun, PlayCard, PlayOption, RunStats } from '../types/game-geo';

// Public identity of the game, and the only place a rename touches: the route
// directory matches on SLUG (src/params/campusQuest.ts) instead of naming it,
// and links, share lines and specs read PATH. Module names, storage keys, API
// routes and tables stay name-agnostic.
export const BRAND = 'CampusQuest';
export const SLUG = 'campus-quest';
export const PATH = `/${SLUG}`;

export const KINDS: CardKind[] = [
	'country-card',
	'intruder-card',
	'nearest-card',
	'city-card',
	'local-card'
];

// The pair on screen is the instruction: each kind asks one question, always,
// so nothing needs a label. `prompt`/`options` say how each side reads;
// `stress` is the one word of the question that flips its meaning.
export const QUESTIONS: Record<
	CardKind,
	{
		above: string;
		below: string;
		stress?: string;
		prompt: 'institution' | 'country' | 'city';
		options: 'country' | 'institution' | 'city';
	}
> = {
	'country-card': {
		above: 'Where is',
		below: 'actually?',
		prompt: 'institution',
		options: 'country'
	},
	'city-card': { above: 'Which city is', below: 'in?', prompt: 'institution', options: 'city' },
	'nearest-card': {
		above: 'Which is closest to',
		below: '?',
		prompt: 'institution',
		options: 'institution'
	},
	'intruder-card': {
		above: 'Which is not in',
		below: '?',
		stress: 'not',
		prompt: 'country',
		options: 'institution'
	},
	'local-card': { above: 'Which is in', below: '?', prompt: 'city', options: 'institution' }
};

// The daily is the same ten kinds in the same order every day, so the rhythm
// is learnable, and the kinds interleave so the opening cards are all
// different; a kind whose pack runs short is filled from the kind with the
// fewest cards dealt so far.
export const DAILY_RECIPE: CardKind[] = [
	'country-card',
	'intruder-card',
	'nearest-card',
	'city-card',
	'local-card',
	'country-card',
	'intruder-card',
	'nearest-card',
	'city-card',
	'country-card'
];
export const DAILY_SIZE = DAILY_RECIPE.length;
export const LIVES = 5;

// Scores count half-points: a plain hit is FULL, a hit after the 50:50 HALF
// (0.5 x 0.5 = 0.25 is what a blind guess at four options is worth, so the
// lifeline buys certainty, never score).
export const FULL = 2;
export const HALF = 1;

// One clock for every card, whatever it reads; the lifeline restarts it.
export const RUN_SECONDS = 15;

// Hospitals and medical schools are a quarter of the misdirect pack; a daily
// admits only a few so a run reads as institutions, not wards.
export const MAX_MEDICAL_CARDS = 3;
const MEDICAL_RE =
	/\b(hospitals?|hôpital|hopital|ospedale|hospice|clinics?|clínic|klinik|infirmary|medicine|medical|health|sjukhus|sairaala|sygehus|ziekenhuis|krankenhaus)\b/i;

export function livesLeft(missed: number): number {
	return Math.max(0, LIVES - missed);
}

export function isMedicalName(name: string): boolean {
	return MEDICAL_RE.test(name);
}

export function promptLabel(card: Pick<PlayCard, 'kind' | 'prompt'>): string {
	return QUESTIONS[card.kind].prompt === 'country'
		? `${ccFlag(card.prompt)} ${ccName(card.prompt)}`
		: card.prompt;
}

// The question's opening line split around its stressed word: [before, word, after].
export function askParts(kind: CardKind): [string, string, string] {
	const q = QUESTIONS[kind];
	if (!q.stress) return [q.above, '', ''];
	const at = q.above.indexOf(q.stress);
	return [q.above.slice(0, at), q.stress, q.above.slice(at + q.stress.length)];
}

// The reveal's headline flag: the answer's country on a country card, the
// intruder's real country on an intruder card.
export function revealFlag(card: PlayCard): string {
	if (card.kind === 'country-card') return ccFlag(card.answer);
	if (card.kind === 'intruder-card') return ccFlag(card.cc);
	return '';
}

// The line under the reveal's answer: where the answer sits in relation to
// the question — the intruder's real place, the nearest option's distance,
// otherwise the prompt itself.
export function revealSub(card: PlayCard): string {
	switch (card.kind) {
		case 'intruder-card':
			return [card.city, ccName(card.cc)].filter(Boolean).join(', ');
		case 'nearest-card': {
			const km = card.options.find((o) => o.key === card.answer)?.km;
			return km === undefined ? card.prompt : `${km} km from ${card.prompt}`;
		}
		default:
			return promptLabel(card);
	}
}

// The miss recap names the question, not just the prompt: "not in France",
// "in Hangzhou", "closest to X", or the institution asked about.
export function missPrompt(card: PlayCard): string {
	switch (card.kind) {
		case 'intruder-card':
			return `not in ${promptLabel(card)}`;
		case 'local-card':
			return `in ${card.prompt}`;
		case 'nearest-card':
			return `closest to ${card.prompt}`;
		default:
			return card.prompt;
	}
}

export function optionLabel(kind: CardKind, option: PlayOption): string {
	return QUESTIONS[kind].options === 'country' ? ccName(option.label) : option.label;
}

export function answerLabel(card: PlayCard): string {
	const o = card.options.find((x) => x.key === card.answer);
	return o ? optionLabel(card.kind, o) : card.answer;
}

// The two options the 50:50 leaves: the answer and one wrong option, picked
// by hash so the same card keeps the same pair all day.
export function lifelineKeep(card: PlayCard, day: string): string[] {
	const wrong = card.options
		.filter((o) => o.key !== card.answer)
		.sort(
			(a, b) => fnv1a(`${day}|${card.semId}|${a.key}`) - fnv1a(`${day}|${card.semId}|${b.key}`)
		);
	return [card.answer, wrong[0].key];
}

export function points(hit: boolean, lifelined: boolean): number {
	return hit ? (lifelined ? HALF : FULL) : 0;
}

export function formatPoints(halves: number): string {
	const whole = Math.floor(halves / FULL);
	return halves % FULL ? `${whole}½` : `${whole}`;
}

// 🟩 placed, 🟨 placed on the lifeline, 🟥 missed or timed out.
export function gridLine(deckIds: string[], missed: string[], lifelined: string[]): string {
	return deckIds
		.map((id) => (missed.includes(id) ? '🟥' : lifelined.includes(id) ? '🟨' : '🟩'))
		.join('');
}

export function runShareText(day: string, score: number, outOf: number, grid: string): string {
	return shareMessage(BRAND, day, `${grid} ${formatPoints(score)}/${outOf}`, PATH);
}

export function verdictLine(score: number, outOf: number): string {
	if (score === outOf * FULL) return `Perfect — all ${outOf} placed`;
	if (score === 0) return `None of the ${outOf} placed`;
	return `${formatPoints(score)} of ${outOf} placed`;
}

// The daily deck is the same for every player: cards rank by a hash of the
// day and their id (rendezvous order), so the pick is deterministic without a
// pin table and a card added or pulled mid-day shifts at most one slot of its
// kind. Option order hashes the same way. An anchor carries one card per
// kind in the pack but plays at most once per deck: a second card would give
// the first away, and runs are keyed by anchor.
export function dailyDeck(pack: PlayCard[], day: string): PlayCard[] {
	const key = (s: string) => fnv1a(`${day}|${s}`);
	const queues = new Map<CardKind, PlayCard[]>(KINDS.map((k) => [k, []]));
	for (const c of [...pack].sort(
		(a, b) => key(`${a.semId}|${a.kind}`) - key(`${b.semId}|${b.kind}`)
	))
		queues.get(c.kind)?.push(c);
	const deck: PlayCard[] = [];
	const anchors = new Set<string>();
	const dealt = new Map<CardKind, number>(KINDS.map((k) => [k, 0]));
	let medical = 0;
	const take = (kind: CardKind): boolean => {
		const queue = queues.get(kind) ?? [];
		while (queue.length) {
			const c = queue.shift() as PlayCard;
			if (anchors.has(c.semId)) continue;
			if (isMedicalName(c.name)) {
				if (medical === MAX_MEDICAL_CARDS) continue;
				medical += 1;
			}
			anchors.add(c.semId);
			dealt.set(kind, (dealt.get(kind) ?? 0) + 1);
			deck.push(c);
			return true;
		}
		return false;
	};
	const fewestDealtFirst = () =>
		[...KINDS].sort((a, b) => (dealt.get(a) ?? 0) - (dealt.get(b) ?? 0));
	for (const kind of DAILY_RECIPE) {
		if (!take(kind)) fewestDealtFirst().some(take);
	}
	return deck.map((c) => ({
		...c,
		options: [...c.options].sort((a, b) => key(`${c.semId}|${a.key}`) - key(`${c.semId}|${b.key}`))
	}));
}

// Survival runs every anchor once in a fresh random order (a random one of
// its kinds), option order alike; the run ends on the last life or the last card.
export function survivalDeck(pack: PlayCard[]): PlayCard[] {
	const anchors = new Set<string>();
	return shuffle(pack)
		.filter((c) => !anchors.has(c.semId) && anchors.add(c.semId))
		.map((c) => ({ ...c, options: shuffle(c.options) }));
}

// One histogram bucket per whole point of the daily (a half rounds down).
export function runStats(runs: DailyRun[]): RunStats {
	const hist = Array.from({ length: DAILY_SIZE + 1 }, () => 0);
	let total = 0;
	let best = 0;
	for (const r of runs) {
		hist[Math.min(Math.floor(r.score / FULL), DAILY_SIZE)] += 1;
		total += r.score;
		best = Math.max(best, r.score);
	}
	const avg = runs.length ? Math.round((total / runs.length / FULL) * 10) / 10 : 0;
	return { played: runs.length, best, avg, hist };
}
