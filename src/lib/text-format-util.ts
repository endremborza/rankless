export function formatNumber(n: number) {
    if (n > 1e6) {
        return `${(n / 1e6).toFixed(1)}M`;
    } else if (n > 1e3) {
        return `${(n / 1e3).toFixed(1)}k`;
    } else {
        return n.toFixed(0);
    }
}

export function formatTextToLines(s: string, width: number, height: number, heightMultiplier = 1.2, widthMultiplier = 0.59) {

    const horizontal = formatTextToLinesOneWay(s, width, height, heightMultiplier, widthMultiplier);
    //const vertical = { fontSize: 0 }
    const vertical = formatTextToLinesOneWay(s, height, width, heightMultiplier, widthMultiplier);
    if (horizontal.fontSize >= vertical.fontSize) {
        return { rotate: false, ...horizontal }
    } else {
        return { rotate: true, ...vertical }
    }
}


function formatTextToLinesOneWay(s: string, width: number, height: number, heightMultiplier: number, widthMultiplier: number) {

    let numOfLines = 1;
    let lines = [s]
    const words = s.split(" ")
    let maxLineLen, widthBasedFontSize, heightBasedFontSize, fontSize: number = 0;
    for (const _ of Array(7)) {
        maxLineLen = lines.reduce((a, b) => Math.max(a, b.length), -Infinity);
        widthBasedFontSize = width / (maxLineLen * widthMultiplier)
        heightBasedFontSize = height / (numOfLines * heightMultiplier)
        fontSize = Math.min(widthBasedFontSize, heightBasedFontSize)
        if (fontSize >= (height / ((numOfLines + 1) * heightMultiplier))) {
            return { lines, fontSize }
        }
        lines = splitToLines(words, s.length, numOfLines + 1);
        if (numOfLines == lines.length) {
            break;
        }
        numOfLines = lines.length
    }
    return { lines, fontSize }

}

function splitToLines(words: string[], sLen: number, numOfLines: number) {
    const lines = [];
    let line = []
    let lineLen = 0
    const maxPossLineLen = (sLen / numOfLines) * 1.15;
    for (const word of words) {
        lineLen += word.length + 1
        if ((lineLen > maxPossLineLen) && (line.length > 0)) {
            lines.push(line.join(" "))
            line = []
            lineLen = word.length + 1
        }
        line.push(word)
    }
    if (line.length > 0) {
        lines.push(line.join(" "))
    }
    return lines
}