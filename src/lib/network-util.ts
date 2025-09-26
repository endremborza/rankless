export function getIndex(i: number, j: number, n: number) {
	if (i === j) return -1;
	if (i > j) [i, j] = [j, i];
	let idx = n * i - i - i * (i - 1) / 2
	return idx + j - i - 1
}

export function circleLayout(nodes: string[], edgeWeights: number[], { height = 400, width = 400 }) {
	const cx = width / 2;
	const cy = height / 2;
	return nodes.map((_, i) => {
		const angle = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
		return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
	});
}


export function radialWeightedLayout(nodes: string[], edgeWeights: number[], { height = 400, width = 400 }) {
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

// cytoscape-fcose-headless.ts
import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";

// register once
if (!(cytoscape as any)._fcoseRegistered) {
	cytoscape.use(fcose);
	(cytoscape as any)._fcoseRegistered = true;
}

type FcoseOptions = {
	width?: number;
	height?: number;
	initialTemp?: number,
	coolingFactor?: number,
	minTemp?: number,
	idealEdgeLength?: number;
	nodeRepulsion?: number;
	edgeElasticity?: number;
	nestingFactor?: number;
	gravity?: number;
	numIter?: number;
	// extras
	animate?: boolean;
	randomize?: boolean;
	tile?: boolean;
	spacingFactor?: number;
};

export function cytoscapeLayout(
	nodes: string[],
	edgeWeights: number[],
	opts: FcoseOptions = {}
) {
	const {
		width = 400,
		height = 400,
		numIter = 1000,
		gravity = 1,
		initialTemp = 1000,
		coolingFactor = 0.99,
		minTemp = 1,
		// idealEdgeLength = 100,
		// nodeRepulsion = 4000,
		// edgeElasticity = 100,
		// nestingFactor = 1.2,
		// spacingFactor = 1.0,
		// force animations off for headless
		animate = false,
		randomize = true,
		tile = false,
	} = opts;

	const n = nodes.length;
	if (n === 0) return [];

	// build elements
	const elements: cytoscape.ElementDefinition[] = nodes.map((id) => ({ data: { id } }));
	let idx = 0;
	for (let i = 0; i < n; i++) {
		for (let j = i + 1; j < n; j++) {
			const w = edgeWeights[idx++] || 0;
			if (w > 0) elements.push({ data: { source: nodes[i], target: nodes[j], weight: w } });
		}
	}

	// create cytoscape headless instance (no DOM)
	const cy = cytoscape({
		headless: true,
		elements,
	});

	// fcose layout options — keep animate false in headless mode
	const layout = cy.layout({
		name: "fcose",
		// core tuning
		animate,
		randomize,
		gravity,
		numIter,
		initialTemp,
		coolingFactor,
		minTemp,
		idealEdgeLength: 50,
		nodeRepulsion: 100_000,
		// edgeElasticity,
		// nestingFactor,
		// fcose uses 'spacingFactor' rather than padding for internal gaps;
		// we'll still use padding later for final bounding box
		// spacingFactor,
		tile,
	} as any);

	layout.run();

	// extract positions
	let positions = nodes.map((id) => {
		const pos = cy.getElementById(id).position();
		return { x: pos.x, y: pos.y };
	});

	// normalize & scale to requested width/height with the given padding
	const xs = positions.map((p) => p.x);
	const ys = positions.map((p) => p.y);
	let minX = Math.min(...xs);
	let maxX = Math.max(...xs);
	let minY = Math.min(...ys);
	let maxY = Math.max(...ys);

	if (!isFinite(minX) || !isFinite(minY)) {
		// fallback: random spread if fcose returned bad coords
		positions = nodes.map((_, i) => ({
			x: (i % 10) * (width / Math.min(10, n)),
			y: Math.floor(i / 10) * (height / Math.ceil(n / 10)),
		}));
		minX = Math.min(...positions.map(p => p.x));
		maxX = Math.max(...positions.map(p => p.x));
		minY = Math.min(...positions.map(p => p.y));
		maxY = Math.max(...positions.map(p => p.y));
	}

	// avoid zero range
	if (maxX - minX < 1) { minX -= 0.5; maxX += 0.5; }
	if (maxY - minY < 1) { minY -= 0.5; maxY += 0.5; }

	const scaleX = width / (maxX - minX);
	const scaleY = height / (maxY - minY);
	const scale = Math.min(scaleX, scaleY);

	// center offset (so graph is centered inside the inner rectangle)
	const usedW = (maxX - minX) * scale;
	const usedH = (maxY - minY) * scale;
	const offsetX = (width - usedW) / 2;
	const offsetY = (height - usedH) / 2;

	positions = positions.map(p => ({
		x: (p.x - minX) * scale + offsetX,
		y: (p.y - minY) * scale + offsetY,
	}));

	return positions;
}
