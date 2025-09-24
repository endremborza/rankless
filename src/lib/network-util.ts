export function getIndex(i: number, j: number, n: number) {
	if (i === j) return -1;
	if (i > j) [i, j] = [j, i];
	let idx = 0;
	for (let hi = 0; hi < i; hi++) {
		idx += n - hi - 1
	}
	return idx + j - i - 1
}

export function circleLayout(nodes: string[], edgeWeights: number[], size = 400) {
	const cx = size / 2;
	const cy = size / 2;
	const radius = Math.min(size, 400) * 0.35;
	return nodes.map((_, i) => {
		const angle = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
		return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
	});
}


export function radialWeightedLayout(nodes: string[], edgeWeights: number[], size = 400) {
	const cx = size / 2;
	const cy = size / 2;
	const maxR = Math.min(size, 400) * 0.35;

	// weighted degree
	const weights = nodes.map((_, i) =>
		nodes.reduce((sum, _, j) => {
			if (i === j) return sum;
			const idx = i < j ? i * nodes.length + j - 1 : j * nodes.length + i - 1;
			return sum + (edgeWeights[idx] || 0);
		}, 0)
	);

	const maxW = Math.max(...weights) || 1;
	return nodes.map((_, i) => {
		const angle = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
		const r = maxR * (1 - weights[i] / maxW); // strong = center
		return { x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r };
	});
}


export function forceDirectedLayout(
	nodes: string[],
	edgeWeights: number[],
	size = 400,
	iterations = 200,
) {
	const n = nodes.length;
	if (n === 0) return [];

	const cx = size / 2;
	const cy = size / 2;
	const area = size * size;
	const k = Math.sqrt(area / n);

	// start in a circle
	let pos = circleLayout(nodes, edgeWeights, size);
	for (let iter = 0; iter < iterations; iter++) {
		const disp = pos.map(() => ({ x: 0, y: 0 }));

		// repulsive forces
		for (let i = 0; i < n; i++) {
			for (let j = i + 1; j < n; j++) {
				let dx = pos[i].x - pos[j].x;
				let dy = pos[i].y - pos[j].y;
				let dist = Math.sqrt(dx * dx + dy * dy) + 0.01;
				let force = (k * k) / dist;
				disp[i].x += (dx / dist) * force;
				disp[i].y += (dy / dist) * force;
				disp[j].x -= (dx / dist) * force;
				disp[j].y -= (dy / dist) * force;
			}
		}

		// attractive forces
		for (let i = 0; i < n; i++) {
			for (let j = i + 1; j < n; j++) {
				const idx = getIndex(i, j, n);
				const w = edgeWeights[idx] || 0;
				if (w <= 0) continue;
				let dx = pos[i].x - pos[j].x;
				let dy = pos[i].y - pos[j].y;
				let dist = Math.sqrt(dx * dx + dy * dy) + 0.01;
				let force = (dist * dist) / (k / Math.sqrt(w));
				disp[i].x -= (dx / dist) * force;
				disp[i].y -= (dy / dist) * force;
				disp[j].x += (dx / dist) * force;
				disp[j].y += (dy / dist) * force;
			}
		}

		// apply displacement
		for (let i = 0; i < n; i++) {
			pos[i].x += disp[i].x * 0.01;
			pos[i].y += disp[i].y * 0.01;
		}
	}

	// recenter to canvas center
	const avgX = pos.reduce((s, p) => s + p.x, 0) / n;
	const avgY = pos.reduce((s, p) => s + p.y, 0) / n;
	pos = pos.map((p) => ({
		x: p.x + (cx - avgX),
		y: p.y + (cy - avgY),
	}));

	// clip to [0, size]
	pos = pos.map((p) => ({
		x: Math.max(0, Math.min(size, p.x)),
		y: Math.max(0, Math.min(size, p.y)),
	}));

	return pos;
}
