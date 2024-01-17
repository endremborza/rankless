<script lang="ts">
	export let rotScaler: number = 1;

	const nP = 7;
	const pRels = [];

	for (let i = 0; i < nP; i++) {
		const phi = (Math.PI / nP) * i * 2;
		let vec = { x: Math.cos(phi), y: Math.sin(phi) };
		pRels.push(vec);
	}
	const pathExt = pRels.map((e) => `l ${e.x} ${e.y}`).join(' ');

	type IconGroup = { colors: string[]; opacities: number[]; startRot: number };

	function getGrots(iconGroup: IconGroup, rotScaler: number) {
		const gRots: { rot: number; s: number; color: string; opacity: number }[] = [];
		for (const [i, color] of iconGroup.colors.entries()) {
			gRots.push({
				rot: rotScaler * (60 + iconGroup.startRot + i * 3),
				s: Math.pow(1.02, i * rotScaler),
				color,
				opacity: iconGroup.opacities[i] || 1
			});
		}

		gRots.reverse();
		return gRots;
	}

	const color1 = '--color-theme-white';
	const color2 = '--color-theme-yellow';
	const color3 = '--color-theme-darkblue';

	const shapeD1 =
		'M299.139 81.1881C382.696 81.1665 409.202 -45.1147 466.202 18.1881C521.516 79.6189 471.71 220.18 466.202 304C533.703 531.5 617.001 609.5 516.501 609.5C327.798 609.5 386.299 723 312.001 661C237.704 599 387.708 442.916 342.001 406C283.489 358.742 75.5016 548.5 4.50065 406C-18.9991 262 62.3634 279.5 95.9998 192.5C162.5 20.5 215.604 81.2097 299.139 81.1881Z';

	const shapeD2 =
		'M217.83 87.0001C289.886 86.9815 389.497 22.0616 438.651 76.652C486.352 129.628 443.401 228.584 438.651 300.868C496.861 497.057 355.433 510.423 331.717 534.139C285.312 572.585 362.072 632.677 303.69 621.238C254.584 611.616 226.687 573.736 187.271 541.901C136.813 501.147 62.6584 641.935 6.17366 362.959C-21.8521 92.6059 57.3866 191.169 106.208 138.311C225.647 -138.079 145.792 87.0188 217.83 87.0001Z';

	const shapeD3 =
		'M245.829 70C317.885 69.9814 340.744 -38.9196 389.899 15.6708C437.599 68.6468 471.4 211.584 466.65 283.868C524.86 480.057 484.759 454.004 413.863 524.901C367.458 563.347 273.652 601.448 215.27 590.009C166.163 580.387 254.686 556.736 215.27 524.901C164.812 484.147 0.109375 569.743 0.109375 398.563C0.108932 182.108 7.77318 259.975 56.5942 207.117C176.034 -69.2727 173.791 70.0186 245.829 70Z';

	const shapeD4 =
		'M252.437 63.1884C335.993 63.1669 436.501 38.1972 493.5 101.5C548.813 162.931 514.008 227.369 508.5 311.189C576 538.689 488.501 518.499 461 546C407.188 590.583 490.199 696.765 422.5 683.5C365.557 672.342 333.351 673.552 293.5 613C178 437.5 94 683.5 7.00111 383.189C-25.4974 69.6889 66.3874 183.982 123 122.688C231.5 -111 168.902 63.21 252.437 63.1884Z';

	function aFill<T>(fills: [number, T][]): T[] {
		const o = [];
		for (const [n, e] of fills) {
			o.push(...Array(n).fill(e));
		}
		return o;
	}

	const iconGroups: IconGroup[] = [
		{
			colors: aFill([
				[3, color1],
				[6, color2],
				[2, color3]
			]),
			opacities: aFill([
				[9, 1],
				[2, 0.2]
			]),
			startRot: 0
		},
		{
			colors: aFill([
				[3, color1],
				[8, color3]
			]),
			opacities: aFill([
				[8, 1],
				[1, 0.5],
				[2, 0.2]
			]),
			startRot: 15
		}
	];

	$: grotGroups = iconGroups.map((e) => getGrots(e, rotScaler));
	//filter: drop-shadow(0px 2px 28px rgba(15, 98, 254, 0.33));

	const bgPaths = [
		{ scale: 170, x: 290, y: 320, path: { d: shapeD4, fill: '--color-theme-purple' } },
		{ scale: 170, x: 340, y: 310, path: { d: shapeD1, fill: '--color-theme-lightgrey' } }
	];
	function bgToMatrix(bgPath: { scale: number; y: number; x: number }) {
		const s = 1 / bgPath.scale;
		return `matrix(${s}, 0, 0, ${s}, ${-bgPath.x * s}, ${-bgPath.y * s})`;
	}
</script>

{#each bgPaths as bgPath, i}
	<g style="transform: {bgToMatrix(bgPath)}" fill-opacity="0.8">
		<path id="bg-path-{i}" d={bgPath.path.d} fill="var({bgPath.path.fill})" />
	</g>
{/each}

{#each grotGroups as gRots}
	<g id="xagon-side">
		{#each gRots as gRot}
			<g
				stroke="var({gRot.color})"
				style="--rotate: {gRot.rot}deg; --scale: {gRot.s}"
				opacity={gRot.opacity}
			>
				<path stroke-width="0.01" fill="none" d="M -0.5 -{Math.cos(Math.PI / nP)} {pathExt} z" />
			</g>
		{/each}
	</g>
{/each}

<style>
	g {
		transition: transform 1.5s;
		transform: rotate(var(--rotate)) scale(var(--scale));
	}

	#xagon-side {
		filter: drop-shadow(0px 0.029px 0.039px rgba(15, 98, 254, 0.53));
		/* rgba(15, 98, 254, 0.53) */
	}

	#bg-path-0 {
		filter: drop-shadow(15px 15px 60px rgba(0, 0, 0, 0.3));
	}
</style>
