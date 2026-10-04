export type Box = { x: number; y: number; w: number; h: number };

// One label to place: its candidate boxes in order of preference, and whether it must be drawn.
export type Placing = { boxes: Box[]; must: boolean };

// Whether two boxes come within the margins of each other.
export function overlaps(a: Box, b: Box, mx = 0, my = 0): boolean {
	return (
		a.x < b.x + b.w + mx && b.x < a.x + a.w + mx && a.y < b.y + b.h + my && b.y < a.y + a.h + my
	);
}

// Greedy in the items' order: each takes its first box that clashes with no box placed before it
// and with none of its blockers (the boxes in its way, which may depend on the items dropped so
// far). With no such box a `must` item settles for its first box clear of the placed ones, failing
// that for its first, and any other item is dropped. The index of each item's box, null if dropped.
export function placeGreedy(
	items: Placing[],
	blockers: (i: number, dropped: ReadonlySet<number>) => Box[],
	clashes: (a: Box, b: Box) => boolean = (a, b) => overlaps(a, b)
): (number | null)[] {
	const taken: Box[] = [];
	const dropped = new Set<number>();
	const clearOf = (boxes: Box[]) => (c: Box) => !boxes.some((b) => clashes(b, c));
	return items.map(({ boxes, must }, i) => {
		let pick = boxes.findIndex(clearOf([...taken, ...blockers(i, dropped)]));
		if (pick < 0 && must && boxes.length > 0) pick = Math.max(0, boxes.findIndex(clearOf(taken)));
		if (pick < 0) {
			dropped.add(i);
			return null;
		}
		taken.push(boxes[pick]);
		return pick;
	});
}
