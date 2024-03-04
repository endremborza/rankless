<script lang="ts">
	import { getSankeyPath } from '$lib/visual-util';

	let topY = 5.6;
	let pLen = 9;

	$: y = topY + pLen;
	$: botL = 20 - 1 - y;
	$: topL = topY - 1;

	$: d1 = getSankeyPath({ x: 4, y: topY }, { x: 1, y }, { parent: 0.7, child: 4.5 }, botL, topL);
	$: d2 = getSankeyPath({ x: 5.5, y: topY }, { x: 8.3, y }, { parent: 0.6, child: 11 }, botL, topL);
	$: d3 = getSankeyPath({ x: 7, y: topY }, { x: 2.2, y }, { parent: 1, child: 3.3 }, botL, topL);
</script>

<path
	d={d2}
	fill="var(--color-theme-darkblue)"
	stroke-width="0.2"
	stroke="var(--color-theme-darkblue)"
/>
<path d={d1} fill="none" stroke-width="0.3" stroke="var(--color-theme-darkblue)" />
<path d={d3} fill="none" stroke-width="0.2" stroke="var(--color-theme-darkgrey)" />
