import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit()],
	server: { fs: { allow: ['static'] }, watch: { ignored: ['**/target/**'] } },
	ssr: { external: ['bun:sqlite'] },
	build: { rollupOptions: { external: ['bun:sqlite'] } },
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
