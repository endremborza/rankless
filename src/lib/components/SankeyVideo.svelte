<script lang="ts">
	import {getSankeyPath} from '$lib/visual-util';

	// 7
	// 4 block changes
	// 2 opened changes
	const w = 20;
	const h = w / 2;

	let blurFrames = [
		[0, 0, 0, 0, 0, 0, 0],
		[0, 0, 0, 0, 0, 0, 0],
		[0, 0.1, 0, 0.2, 0.1, 0.2, 0.1],
		[0, 0.2, 0.1, 0.3, 0, 0.3, 0.2],
		[0.1, 0.1, 0.2, 0.1, 0.2, 0.1, 0.1],
		[0, 0, 0, 0, 0, 0, 0]
	];

	function getPaths(
		sizes: number[],
		pad: number,
		topDivider: number,
		topShift: number,
		reach: number
	) {
		let topOffset = 0;
		let bottomOffset = 0;
		const totalW = w + pad * (sizes.length - 1);
		const s = sizes.reduce((l, r) => l + r);
		const ds = [];
		for (let i = 0; i < sizes.length; i++) {
			let child = (sizes[i] * totalW) / s;
			let parent = child / topDivider;
			ds.push(
				getSankeyPath(
					{x: topOffset + topShift, y: reach},
					{x: bottomOffset, y: reach + h / 2},
					{parent, child},
					h * 2,
					h * 2 + reach
				)
			);
			topOffset += pad + parent;
			bottomOffset += pad + child;
		}
		return ds;
	}

	const setups = [
		[[8, 3, 7, 1, 5, 2, 4], 0, 1, 0, h * 2],
		[[8, 3, 7, 1, 5, 2, 4], 0, 1, 0, h * 2],
		[[3, 4, 6, 3, 1, 5, 2], 0.2, 2, 3, h * 2],
		[[8, 3, 7, 1, 5, 2, 4], 0.4, 2.5, 3, h * 2],
		[[8, 3, 7, 1, 5, 2, 4], 0.3, 3, 3, h / 2],
		[[8, 3, 7, 1, 5, 2, 4], 0.2, 2.3, 3, h / 2],
		[[8, 3, 7, 1, 5, 2, 4], 0, 1, 0, h * 2]
	];

	let paths: string[][] = setups.map((e) => getPaths(...e));
</script>

<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
	<defs>
		{#each paths as _, i}
		<filter id="f{i}" x="0" y="0" xmlns="http://www.w3.org/2000/svg">
			<feGaussianBlur id="blur{i}" in="SourceGraphic" stdDeviation="0" />
		</filter>
		{/each}
	</defs>
	{#each paths[0] as ds, i}
	<path id="p{i}" d={ds[0]} style="fill: rgb(var(--color-range-{i * 10 + 5}))" filter="url(#f{i}" />

	<animate xlink:href="#blur{i}" attributeName="stdDeviation" values={blurFrames.map((l)=> l[i]).join(';')}
		dur="3s"
		begin="0s"
		repeatCount="indefinite"
		/>

		<animate xlink:href="#p{i}" attributeName="d" values={paths.map((l)=> l[i]).join(';')}
			dur="18s"
			begin="0s"
			repeatCount="indefinite"
			/>
			{/each}
</svg>

<style>
	svg {
		opacity: 30%;
		position: fixed;
		top: -20lvh;
		width: 100%;
		height: 120lvh;
		z-index: -2;
	}
</style>
