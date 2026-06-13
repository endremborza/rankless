import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit()],
	server: { fs: { allow: ['static'] }, watch: { ignored: ['**/target/**'] } },
	ssr: { external: ['bun:sqlite'] },
	build: {
		rollupOptions: {
			external: ['bun:sqlite'],
			output: {
				// keep the heavy graph-layout vendor code in one lazy chunk (loaded via
				// the dynamic import in AuthorNetwork.svelte, never on initial paint)
				manualChunks: (id) =>
					/node_modules\/(cytoscape|cose-base|layout-base)/.test(id) ? 'cytoscape' : undefined
			}
		},
		// the only chunk above 500 kB is the lazy cytoscape vendor chunk (~566 kB)
		chunkSizeWarningLimit: 600,
		// Inline maps for the e2e coverage build so monocart can remap V8 coverage
		// (browser + SSR) back to .svelte/.ts without fetching external .map files.
		sourcemap: process.env.COVERAGE ? 'inline' : false
	},
	test: {
		include: ['src/**/*.test.ts'],
		coverage: {
			provider: 'v8',
			// Unit tests target the TS logic in src/lib; .svelte components are
			// exercised by the Playwright e2e suite, not vitest, so including them
			// here would only dilute the numbers with unreachable 0% rows.
			include: ['src/lib/**/*.ts'],
			exclude: ['src/lib/**/*.test.ts'],
			reporter: ['text', 'html'],
			reportsDirectory: './coverage'
		}
	}
});
