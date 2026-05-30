declare module 'cytoscape-fcose';

declare module 'bun:sqlite' {
	export class Database {
		constructor(filename?: string);
		run(sql: string, ...params: unknown[]): void;
		prepare(sql: string): Statement;
	}
	export interface Statement {
		get(...params: unknown[]): unknown;
		all(...params: unknown[]): unknown[];
		run(...params: unknown[]): { changes: number; lastInsertRowid: number | bigint };
	}
}
