/** @type {import('./$types').EntryGenerator} */
export function entries() {
    return [
        { qcId: 'init-qc' },
        { qcId: 'shuf-qc' },
        { qcId: 'shorter-qc' }
    ]
}

export const prerender = true;
