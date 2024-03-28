<script lang="ts">
	export let size = 3;
	export let rotated = 0;

	let topRate = 0.13;

	let tSideRate = 0.15;
	let tBottomRate = 0.78; // 0.7
	let tTopRate = 0.34; //0.2

	let tStroke = 0.08;

	$: tTop = size * tTopRate;
	$: bSide = size * topRate;

	//#92C1FF

	//#92B7E8
</script>

<path d="M0 0 H{size} V{size} H0 V0 Z" fill="var(--color-theme-blue)" fill-opacity="0.7" />

<path d="M0 {bSide} H{size} V0 H0 V0 Z" fill="var(--color-theme-lightblue)" />

<g style="--rot: {rotated}deg; --rx: {size / 2}px; --ry: {(size * (tTopRate + tBottomRate)) / 2}px">
	<path
		d="M{size * tSideRate} {tTop} L{size * 0.5} {size * tBottomRate} L{size *
			(1 - tSideRate)} {tTop}"
		stroke="var(--color-theme-white)"
		stroke-width={tStroke * size}
		stroke-linecap="round"
		stroke-linejoin="round"
		fill="none"
	/>
</g>

<style>
	path {
		cursor: pointer;
	}

	g {
		transform: rotate(var(--rot));
		transform-origin: var(--rx) var(--ry);
		cursor: pointer;
	}
</style>
