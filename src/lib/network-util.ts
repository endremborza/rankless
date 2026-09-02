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
