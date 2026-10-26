// The force layout's cooling schedule: the layout's defaults and where the tuning sliders start.
export const COOLING = { initialTemp: 1000, coolingFactor: 0.99, minTemp: 1 };

export function getIndex(i: number, j: number, n: number) {
	if (i === j) return -1;
	if (i > j) [i, j] = [j, i];
	const idx = n * i - i - (i * (i - 1)) / 2;
	return idx + j - i - 1;
}

export type Tie = { i: number; j: number; rate: number };

const HUB_STEPS = 400;

// Positions in a `w`×`h` box, `padX`/`padY` clear of its sides, for `n` nodes around a hub at its
// centre: a Fruchterman–Reingold layout in which every node repels the others and the hub, is tied
// to the hub, and each tie pulls its pair together by its `rate` (0–1). It runs in a square and is
// stretched to the box, so the nodes spread along a long side instead of piling against it. The
// nodes start on a spiral in their order, so a layout is reproducible. O(HUB_STEPS · n²).
export function hubLayout(
	n: number,
	ties: Tie[],
	{ w, h, padX, padY }: { w: number; h: number; padX: number; padY: number }
): { x: number; y: number }[] {
	const [rx, ry] = [w / 2 - padX, h / 2 - padY];
	const half = Math.min(rx, ry);
	const k = Math.sqrt((4 * half * half) / (n + 1));
	const turn = Math.PI * (3 - Math.sqrt(5));
	const pos = Array.from({ length: n }, (_, i) => {
		const s = half * Math.sqrt((i + 1) / n);
		return { x: s * Math.cos(i * turn), y: s * Math.sin(i * turn) };
	});
	for (let step = 0; step < HUB_STEPS; step++) {
		const move = pos.map(() => ({ x: 0, y: 0 }));
		for (let i = 0; i < n; i++) {
			for (let j = i + 1; j < n; j++) {
				const [dx, dy] = [pos[i].x - pos[j].x, pos[i].y - pos[j].y];
				const f = (k * k) / Math.max(dx * dx + dy * dy, 1);
				move[i].x += dx * f;
				move[i].y += dy * f;
				move[j].x -= dx * f;
				move[j].y -= dy * f;
			}
			const { x: dx, y: dy } = pos[i];
			const d = Math.max(Math.hypot(dx, dy), 1);
			const f = (k * k) / (d * d) - d / k;
			move[i].x += dx * f;
			move[i].y += dy * f;
		}
		for (const { i, j, rate } of ties) {
			const [dx, dy] = [pos[i].x - pos[j].x, pos[i].y - pos[j].y];
			const f = (rate * Math.hypot(dx, dy)) / k;
			move[i].x -= dx * f;
			move[i].y -= dy * f;
			move[j].x += dx * f;
			move[j].y += dy * f;
		}
		const heat = k * (1 - step / HUB_STEPS);
		pos.forEach((p, i) => {
			const d = Math.max(Math.hypot(move[i].x, move[i].y), 1e-9);
			const s = Math.min(d, heat) / d;
			p.x = Math.min(Math.max(p.x + move[i].x * s, -half), half);
			p.y = Math.min(Math.max(p.y + move[i].y * s, -half), half);
		});
	}
	return pos.map(({ x, y }) => ({ x: w / 2 + (x * rx) / half, y: h / 2 + (y * ry) / half }));
}

export function circleLayout(
	nodes: string[],
	edgeWeights: number[],
	{ height = 400, width = 400 }
) {
	const cx = width / 2;
	const cy = height / 2;
	const radius = Math.min(cy, cx) * 0.8;
	return nodes.map((_, i) => {
		const angle = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
		return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
	});
}
