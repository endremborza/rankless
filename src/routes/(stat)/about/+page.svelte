<script lang="ts">
	import cclLogo from '$lib/assets/images/icons/ccl-logo.png';
	import corvLogo from '$lib/assets/images/icons/corv-logo.png';
	import udtLogo from '$lib/assets/images/icons/udt-logo.png';

	import euLogo from '$lib/assets/images/icons/ec-logo.png';

	import cesarPortrait from '$lib/assets/images/portraits/cesar.jpg';
	import endrePortrait from '$lib/assets/images/portraits/endre.jpg';
	import veraPortrait from '$lib/assets/images/portraits/vera.jpg';
	import matePortrait from '$lib/assets/images/portraits/mate.jpg';

	import corvPicture from '$lib/assets/images/minified/corvinus-e-saltway.jpg';
	import SankeyVideo from '$lib/components/SankeyVideo.svelte';

	const uLogos = [cclLogo, corvLogo, udtLogo];

	const protraits = [
		{
			src: cesarPortrait,
			name: 'César A. Hidalgo',
			role: 'CCL Director',
			href: 'https://cesarhidalgo.com/'
		},
		{src: endrePortrait, name: 'Endre Borza', role: 'Research Data Engineer'},
		{src: veraPortrait, name: 'Veronika Hamar', role: 'CCL Budapest Executive Director'},
		{src: matePortrait, name: 'Máté Barkóczi', role: 'Design Intern'}
	];
</script>

<SankeyVideo />

<div class="bstrip">
	<h1>The People Behind The Project</h1>
</div>

<p class="btxt">
	Meet our multidisciplinary team from the <a href="https://centerforcollectivelearning.org/">Center for
		Collective Learning</a> research group. Founded in 2010 by Professor Cesar Hidalgo, the group actively
	contributes to the
	development of various areas, including economic complexity, the use of crowdsourcing and computer
	vision methods to understand the physical qualities of cities, and the creation of digital democracy
	platforms.
</p>

<div class="bstrip t5">
	<div class="bar">
		{#each protraits as port}
		<div class="person">
			<img class="portrait" src={port.src} alt={port.name} />
			<p><a href={port.href}>{port.name}</a></p>
			<p>{port.role}</p>
		</div>
		{/each}
	</div>
</div>

<span id="uni-block">
	<p class="btxt">
		The Center for Collective Learning is now based at the Artificial and Natural Intelligence
		Institute (ANITI) at the University of Toulouse and the Corvinus Institute for Advanced Studies
		(CIAS) at Corvinus University in Budapest.
	</p>
	<img class="uni-pic" src={corvPicture} alt="University" />
</span>
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

	p {
		font-weight: 600;
		font-size: 1.2rem;
		max-width: 900px;
		margin-left: auto;
		margin-right: auto;
	}

	.btxt {
		padding-left: 35px;
		padding-right: 35px;
		/* color: var(--color-theme-darkblue); */
		text-shadow: 2px 2px 14px var(--color-theme-pink);
	}

	#uni-block {
		display: block;
		margin-right: auto;
		margin-left: auto;
	}

	.uni-pic {
		/* position: absolute; */
		z-index: -1;
		/* left: 20%; */
		/* top: 20svh; */
		position: relative;
		display: block;
		margin-right: auto;
		margin-left: auto;
		width: 700px;
		max-width: 90%;
		opacity: 85%;
		border-radius: 20px;
		filter: grayscale(50%);
		box-shadow: 7px 7px 17px var(--color-theme-darkgrey);
	}

	.logo {
		width: 180px;
		margin: 50px;
	}

	.bar {
		flex: 0 1 1400px;
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
		height: 274px;
		box-shadow: 7px 7px 17px var(--color-theme-darkgrey);
	}
</style>
