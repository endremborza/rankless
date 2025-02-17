// import adapter from '@sveltejs/adapter-auto';
import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	// Consult https://kit.svelte.dev/docs/integrations#preprocessors
	// for more information about preprocessors
	preprocess: vitePreprocess(),

	kit: {
		adapter: adapter({
			// pages: 'build',
			// assets: 'build',
			// fallback: null,
			// precompress: false,
			// strict: true
		}),
		paths: {
			// base: process.argv.includes('alpha') ? '/academic-impact-explorer' : ''
		}
	}
};

export default config;
