declare module 'cytoscape-fcose';

declare const Bun: {
	zstdCompressSync(data: Uint8Array | string, options?: { level?: number }): Uint8Array;
	zstdDecompressSync(data: Uint8Array): Uint8Array;
};

declare module 'bun:sqlite' {
	export class Database {
		constructor(filename?: string);
		run(sql: string, ...params: unknown[]): void;
		prepare(sql: string): Statement;
		close(): void;
	}
	export interface Statement {
		get(...params: unknown[]): unknown;
		all(...params: unknown[]): unknown[];
		run(...params: unknown[]): { changes: number; lastInsertRowid: number | bigint };
	}
}
