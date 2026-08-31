// Shared plumbing for the games (the clue game, the country game): day identity,
// streak rule, daily pick, shuffling, flags/names, share text, result logging,
// and the localStorage round state. Game-specific math lives in game-clues.ts /
// game-countries.ts.

export function utcDayStamp(date: Date = new Date()): string {
	return date.toISOString().slice(0, 10);
}

// Daily-streak rule: giving up (or missing a day) breaks the streak; a finished
// round extends a streak whose last play was yesterday, else starts a fresh one.
export function nextStreak(prev: number, lastDay: string, day: string, gaveUp: boolean): number {
	if (gaveUp) return 0;
	const yesterday = utcDayStamp(new Date(Date.parse(day) - 24 * 60 * 60 * 1000));
	return lastDay === yesterday ? prev + 1 : 1;
}

export function fnv1a(s: string): number {
	let h = 0x811c9dc5;
	for (let i = 0; i < s.length; i++) {
		h ^= s.charCodeAt(i);
		h = Math.imul(h, 0x01000193);
	}
	return h >>> 0;
}

export function dailyIndex(day: string, cardCount: number): number {
	return fnv1a(day) % cardCount;
}

export function shuffle<T>(items: readonly T[]): T[] {
	const out = [...items];
	for (let i = out.length - 1; i > 0; i--) {
		const j = Math.floor(Math.random() * (i + 1));
		[out[i], out[j]] = [out[j], out[i]];
	}
	return out;
}

export function ccFlag(cc: string): string {
	return [...cc.toUpperCase()]
		.map((c) => String.fromCodePoint(0x1f1e6 + c.charCodeAt(0) - 65))
		.join('');
}

const regionNames =
	typeof Intl !== 'undefined' && 'DisplayNames' in Intl
		? new Intl.DisplayNames(['en'], { type: 'region' })
		: null;

export function ccName(cc: string): string {
	try {
		return regionNames?.of(cc.toUpperCase()) ?? cc.toUpperCase();
	} catch {
		return cc.toUpperCase();
	}
}

export function shareMessage(brand: string, day: string, line: string, path: string): string {
	return `${brand} ${day}\n${line}\nhttps://rankless.org${path}`;
}

export function loadGameState<T>(key: string, fallback: T): T {
	try {
		const raw = localStorage.getItem(key);
		if (raw) return JSON.parse(raw) as T;
	} catch {
		// storage unavailable: play stateless
	}
	return fallback;
}

export function saveGameState(key: string, state: unknown): void {
	try {
		localStorage.setItem(key, JSON.stringify(state));
	} catch {
		// storage unavailable: play stateless
	}
}

// Fire-and-forget play-result log; losing one is fine.
export function postGameLog(path: string, payload: unknown): void {
	fetch(path, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload)
	}).catch(() => {});
}

export async function copyShareText(text: string): Promise<boolean> {
	try {
		await navigator.clipboard.writeText(text);
		return true;
	} catch {
		return false;
	}
}
