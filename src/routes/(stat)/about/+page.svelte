<script lang="ts">
	import cclLogo from '$lib/assets/images/icons/ccl-logo.png';
	import corvLogo from '$lib/assets/images/icons/corv-logo.png';
	import udtLogo from '$lib/assets/images/icons/udt-logo.png';

	import euLogo from '$lib/assets/images/icons/ec-logo.png';

	import cesarPortrait from '$lib/assets/images/portraits/cesar.png';
	import endrePortrait from '$lib/assets/images/portraits/endre.png';
	import veraPortrait from '$lib/assets/images/portraits/vera.png';
	import matePortrait from '$lib/assets/images/portraits/mate.png';

	import corvPicture from '$lib/assets/images/minified/corvinus-e-saltway.jpg';
	import SankeyVideo from '$lib/components/SankeyVideo.svelte';

	const uLogos = [cclLogo, corvLogo, udtLogo];

	const protraits = [
		{src: cesarPortrait, name: 'César A. Hidalgo', role: 'CCL Director'},
		{src: endrePortrait, name: 'Endre Borza', role: 'Research Data Engineer'},
		{src: veraPortrait, name: 'Veronika Hamar', role: 'CCL Budapest Executive Director'},
		{src: matePortrait, name: 'Máté Barkóczi', role: 'Design Intern'}
	];
</script>

<SankeyVideo />

<div class="bstrip">
	<h1>We are a small, multidisciplinary, multi-institution team.</h1>
</div>

<div class="bstrip t4" />

<div class="bstrip t5">
	<div class="bar">
		{#each protraits as port}
		<div class="person">
			<img class="portrait" src={port.src} alt={port.name} />
			<p>{port.name}</p>
			<p>{port.role}</p>
		</div>
		{/each}
	</div>
	<div class="bar">
		<img class="uni-pic" src={corvPicture} alt="University" />
	</div>
</div>

<div class="bstrip">
	{#each uLogos as src}
	<img class="logo" {src} alt="inst-logo" />
	{/each}
	<img class="logo" src={euLogo} alt="European Commission Logo" />
</div>

<style>
	h1 {
		text-align: center;
		margin: 30px;
	}

	.uni-pic {
		display: block;
		margin-left: auto;
		margin-right: auto;
		width: 70%;
		border-radius: 30px;
		flex: 0 0 auto;
	}

	.logo {
		width: 180px;
		margin: 50px;
	}

	.bar {
		flex: 0 1 700px;
		display: flex;
		justify-content: center;
		align-items: center;
		flex-wrap: wrap;
	}

	.person>p {
		text-align: center;
	}

	.portrait {
		margin: 30px;
		height: 280px;
	}
</style>
