import { spawn } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { CARD_H, CARD_W } from '$lib/utils/cards';
import { CARD_CACHE_NAME } from '$lib/paths';

// Social platforms (X, LinkedIn, Facebook, Slack, …) don't render SVG OG images, so every card is
// rasterized to a CARD_W×CARD_H PNG.

// Rendering on every crawler hit spawns a process; a best-effort disk cache keyed by entity+params
// amortizes that for widely-shared cards. process.env (not $env) keeps this module free of
// SvelteKit virtual modules so it unit-tests under plain vitest.
const CACHE_DIR = process.env.CARD_CACHE_DIR ?? join(tmpdir(), CARD_CACHE_NAME);

export async function rasterizeSvg(svg: string, width = CARD_W, height = CARD_H): Promise<Buffer> {
	return await new Promise((resolve, reject) => {
		const proc = spawn('rsvg-convert', ['-f', 'png', '-w', String(width), '-h', String(height)]);
		const out: Buffer[] = [];
		const err: Buffer[] = [];
		proc.stdout.on('data', (chunk: Buffer) => out.push(chunk));
		proc.stderr.on('data', (chunk: Buffer) => err.push(chunk));
		proc.on('error', (e) => reject(new Error(`rsvg-convert unavailable: ${e.message}`)));
		proc.on('close', (code) => {
			if (code === 0) resolve(Buffer.concat(out));
			else reject(new Error(`rsvg-convert exited ${code}: ${Buffer.concat(err).toString()}`));
		});
		proc.stdin.write(svg);
		proc.stdin.end();
	});
}

export async function readCardCache(key: string): Promise<Buffer | null> {
	try {
		return await readFile(pathForKey(key));
	} catch {
		return null;
	}
}

export async function writeCardCache(key: string, buf: Buffer): Promise<void> {
	try {
		await mkdir(CACHE_DIR, { recursive: true });
		const dest = pathForKey(key);
		const tmp = `${dest}.${randomUUID()}.tmp`;
		await writeFile(tmp, buf);
		await rename(tmp, dest);
	} catch {
		// A cache write failure (bad dir, full disk) must never break card serving.
	}
}

function pathForKey(key: string): string {
	return join(CACHE_DIR, `${createHash('sha1').update(key).digest('hex')}.png`);
}
