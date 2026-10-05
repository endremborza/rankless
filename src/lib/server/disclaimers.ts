import { DisclaimerDb } from './db';
import { readManifest } from './manifest';

// A disclaimer is a statement about one data run: it shows only while that run is served, so the
// run that carries a correction retires the note with the data it described. The manifest is read
// only for a profile that has a row.
export function activeDisclaimer(rootType: string, semanticId: string): string | null {
	const row = DisclaimerDb.get(rootType, semanticId);
	return row && row.run_id === readManifest().run_id ? row.text : null;
}
