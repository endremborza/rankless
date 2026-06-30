import { describe, expect, it } from 'vitest';
import { CARD_H, CARD_W, rasterizeSvg, readCardCache, writeCardCache } from './card-raster';

const PNG_MAGIC = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const SAMPLE_SVG =
	'<svg xmlns="http://www.w3.org/2000/svg" width="190" height="100">' +
	'<rect width="190" height="100" fill="#123456"/></svg>';

describe('rasterizeSvg', () => {
	it('renders SVG to a PNG at the requested card dimensions', async () => {
		const png = await rasterizeSvg(SAMPLE_SVG);
		expect(png.subarray(0, 8).equals(PNG_MAGIC)).toBe(true);
		// IHDR width/height are big-endian u32 at byte offsets 16 and 20.
		expect(png.readUInt32BE(16)).toBe(CARD_W);
		expect(png.readUInt32BE(20)).toBe(CARD_H);
	});

	it('rejects on invalid SVG input', async () => {
		await expect(rasterizeSvg('not-svg')).rejects.toThrow();
	});
});

describe('card cache', () => {
	it('round-trips a buffer and misses on an unknown key', async () => {
		const key = `test/${Date.now()}-${process.pid}`;
		const payload = Buffer.from('cached-card-bytes');
		await writeCardCache(key, payload);
		const hit = await readCardCache(key);
		expect(hit?.equals(payload)).toBe(true);
		expect(await readCardCache(`${key}-absent`)).toBeNull();
	});
});
