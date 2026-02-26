const NOBEL_URL = 'https://tmp-borza-public-cyx.s3.amazonaws.com/nobel-to-oa.json.gz';

type NobelJson = {
	winners: { category: string; winners: [number, number][] }[];
};

let cached: Set<number> | undefined;

export async function getNobelOaIds(): Promise<Set<number>> {
	if (cached) return cached;
	try {
		const data: NobelJson = await fetch(NOBEL_URL).then((r) => r.json());
		const s = new Set<number>();
		for (const cat of data.winners) for (const [, oaId] of cat.winners) s.add(oaId);
		cached = s;
		return s;
	} catch {
		return new Set();
	}
}
