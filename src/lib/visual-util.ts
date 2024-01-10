import { linkVertical } from "d3-shape";

export const rectangleLinkPath = linkVertical()
    .source((d) => d.start)
    .target((d) => d.end);

