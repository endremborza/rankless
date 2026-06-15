export function getIndex(i: number, j: number, n: number) {
	if (i === j) return -1;
	if (i > j) [i, j] = [j, i];
	const idx = n * i - i - (i * (i - 1)) / 2;
	return idx + j - i - 1;
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

export function radialWeightedLayout(
	nodes: string[],
	edgeWeights: number[],
	{ height = 400, width = 400 }
) {
	const cx = width / 2;
	const cy = height / 2;
	const maxR = Math.min(width, height) * 0.35;
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
