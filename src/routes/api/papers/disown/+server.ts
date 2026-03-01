import { PaperDb } from '$lib/server/db';
import { authedPaperAction } from '../helpers';

const extractWid = (b: Record<string, unknown>) => typeof b.wid === 'number' ? b.wid : null;

export const POST = authedPaperAction(extractWid, PaperDb.disownPaper.bind(PaperDb));
export const DELETE = authedPaperAction(extractWid, PaperDb.unDisownPaper.bind(PaperDb));
