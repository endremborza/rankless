<script lang="ts">
	import cclLogo from '$lib/assets/images/icons/ccl-logo.png';
	import corvLogo from '$lib/assets/images/icons/corv-logo.png';
	import udtLogo from '$lib/assets/images/icons/udt-logo.png';

	import euLogo from '$lib/assets/images/icons/ec-logo.png';

	import cesarPortrait from '$lib/assets/images/portraits/cesar.jpg';
	import endrePortrait from '$lib/assets/images/portraits/endre.jpg';
	import veraPortrait from '$lib/assets/images/portraits/vera.jpg';
	import matePortrait from '$lib/assets/images/portraits/mate.jpg';

	import SankeyVideo from '$lib/components/SankeyVideo.svelte';
	import { onMount } from 'svelte';
	import { parse } from 'platform';

	let isWeak = false;
	let uInfo: { product?: string; name?: string } = {};

	onMount(() => {
		uInfo = parse(navigator.userAgent);
		if (uInfo.product == 'iPhone' || uInfo.name == 'Safari') {
			isWeak = true;
		}
	});

	const uLogos = [cclLogo, corvLogo, udtLogo];

	const protraits = [
		{
			src: cesarPortrait,
			name: 'César A. Hidalgo',
			role: 'CCL Director',
			href: 'https://cesarhidalgo.com/'
		},
		{ src: endrePortrait, name: 'Endre Borza', role: 'Research Data Engineer' },
		{ src: veraPortrait, name: 'Veronika Hamar', role: 'CCL Budapest Executive Director' },
		{ src: matePortrait, name: 'Máté Barkóczi', role: 'Designer' }
	];

	let w = 40;
	let h = w / 2;
</script>

<h1>Meet the People Behind The Project</h1>
<p class="btxt">
	The idea to develop a platform that grasps the complex nature of the impact of universities came
	from professor Cesar Hidalgo. To bring it to life, he recruited a group of motivated colleagues,
	based in Budapest, Hungary. Endre Borza (Data engineer), Máté Barkóczi (Designer), and Cesar
	Hidalgo have been working together since March 2023 on conceptualization, and on the development
	of Rankless. In September 2023 Veronika Hamar joined the team, as a project manager.
</p>

<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
	<SankeyVideo {w} {h} {isWeak} />
</svg>

<h1>Our Team</h1>

<div class="bstrip" id="person-bar">
	<div class="bar">
		{#each protraits as port}
			<div class="person">
				<img class="portrait" src={port.src} alt={port.name} />
				<p><a href={port.href}>{port.name}</a></p>
				<p class="prole">{port.role}</p>
			</div>
		{/each}
	</div>
</div>
<div class="btxt">
	<p>
		The group is part of the <a href="https://centerforcollectivelearning.org/"
			>Center for Collective Learning</a
		>
		research group. Founded in 2010 by Professor Cesar Hidalgo, the group actively contributes to the
		development of various areas, including economic complexity, the use of crowdsourcing and computer
		vision methods to understand the physical qualities of cities, and the creation of digital democracy
		platforms.
	</p>
	<p>
		The Center for Collective Learning is now based at the Artificial and Natural Intelligence
		Institute (ANITI) at the University of Toulouse and the Corvinus Institute for Advanced Studies
		(CIAS) at Corvinus University in Budapest. It is supported by several European projects,
		including an ERA Chair, the European Lighthouse on Artificial Intelligence for Sustainability
		(ELIAS), and the ObsSea4Clim (Horizon) Ocean Observatory
	</p>

	<p>You can reach us by contacting Veronika directly @ veronika.hamar@uni-corvinus.hu</p>
</div>
<div class="bstrip">
	<iframe title="CCL Launch Video" src="https://www.youtube.com/embed/le75gN3pxPk" />
</div>
<div class="bstrip logo-strip">
	{#each uLogos as src}
		<img class="logo" {src} alt="inst-logo" />
	{/each}
	<img class="logo" src={euLogo} alt="European Commission Logo" />
</div>

<style>
	h1 {
		text-align: center;
		font-size: 2.9rem;
		margin: 30px;
	}

	p {
		font-weight: 600;
		font-size: 1.2rem;
		max-width: 1180px;
		margin-left: auto;
		margin-right: auto;
	}

	svg {
		opacity: 70%;
		height: 45svh;
		width: 100%;
		z-index: -2;
		margin-bottom: 70px;
	}

	iframe {
		width: 800px;
		max-width: 90%;
		height: 400px;
		margin-top: 70px;
		margin-bottom: 40px;
	}

	a {
		text-decoration: none;
		color: var(--color-theme-darkgrey3);
	}

	#person-bar {
		padding-top: 80px;
		padding-bottom: 80px;
		background-color: var(--color-theme-lightblue);
	}

	.btxt {
		font-weight: 400;
		text-align: justify;
		padding-left: 35px;
		padding-right: 35px;
		margin-top: 120px;
		margin-bottom: 60px;
		color: var(--color-theme-darkgrey);
	}

	.btxt > p {
		font-weight: 400;
	}

	.prole {
		font-weight: 300;
	}

	.bar {
		flex: 0 1 1400px;
		display: flex;
		justify-content: center;
		align-items: center;
		flex-wrap: wrap;
	}

	.person > p {
		text-align: center;
	}

	.portrait {
		margin: 30px;
		height: 274px;
		box-shadow: 7px 7px 17px var(--color-theme-darkgrey);
	}
</style>
