import { insertKeepingOrder } from "./tree-functions";
import type { OMap, SelectionOption } from "./tree-types";

export function getTopFzf(term: string, entities: OMap<{ name: string }>, limit: number, emptyShow = false) {
    const out: { name: string; id: string }[] = [];
    if ((term.length == 0) && !emptyShow) {
        return out;
    }
    const lowTerms = term.split(' ').map((e) => e.toLowerCase());
    for (const [elemId, e] of Object.entries(entities)) {
        const eLow = e.name.toLowerCase()
        if (lowTerms.map((t) => eLow.includes(t)).reduce((l, r) => l && r)) {
            out.push({ name: e.name, id: elemId });
            if (out.length >= limit) {
                return out;
            }
        }
    }
    return out;
}


export function getTopFzfInsts(term: string, entities: SelectionOption[], limit: number) {
    //
    const out: { name: string, id: string, papers: number, citations: number }[] = [];
    const lowTerms = term.split(' ').map((e) => e.toLowerCase());
    for (const { id, name, meta } of entities) {
        const eLow = name.toLowerCase()
        if (lowTerms.map((t) => eLow.includes(t)).reduce((l, r) => l && r)) {
            const parsedMeta = JSON.parse(meta || '{}');
            const newEntry = { name, id, papers: parsedMeta.papers || 0, citations: parsedMeta.citations || 0 }
            if ((out.length < limit) || (out[out.length - 1].citations < newEntry.citations)) {
                (out.length >= limit) && out.pop();
                insertKeepingOrder(newEntry, out, (l, r) => r.citations - l.citations);

            }
        }
    }
    return out
}
