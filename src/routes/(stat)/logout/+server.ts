import type { RequestHandler } from '@sveltejs/kit';
import { clearSession } from '$lib/server/session';

export const GET: RequestHandler = (event) => clearSession(event);
