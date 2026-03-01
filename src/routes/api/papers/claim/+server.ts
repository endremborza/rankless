import { PaperDb } from '$lib/server/db';
import { authedPaperAction } from '../helpers';

const extractDoi = (b: Record<string, unknown>) => {
	const doi = b.doi;
	return typeof doi === 'string' && doi.trim() ? doi.trim() : null;
};

export const POST = authedPaperAction(extractDoi, PaperDb.claimPaper.bind(PaperDb));
export const DELETE = authedPaperAction(extractDoi, PaperDb.unClaimPaper.bind(PaperDb));
