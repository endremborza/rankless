import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: { fs: { allow: ['static'] } },
	test: {
		include: ['src/**/*.test.ts'],
		alias: {
			'$lib': '/src/lib',
			'$app': '/src/app'
		}
	}
});
