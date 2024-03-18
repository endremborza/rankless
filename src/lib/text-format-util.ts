export function formatNumber(n: number, maxFix: number = 2) {
    if (n > 1e6) {
        return `${(n / 1e6).toFixed(Math.min(1, maxFix))}M`;
    } else if (n > 1e3) {
        return `${(n / 1e3).toFixed(Math.min(1, maxFix))}k`;
    } else if (n < 1) {
        return n.toFixed(Math.min(2, maxFix));
    } else if (n < 10) {
        return n.toFixed(1);
    } else {
        return n.toFixed(0);
    }
}

export function getStylesForWords(words: string[], width: number, height: number, heightMultiplier: number, widthMultiplier: number, baseFontSize: number, leftAligned: boolean, allowRotation: boolean) {
    const horizontal = formatTextToLinesOneWay(words, width, height, heightMultiplier, widthMultiplier);
    let rotate = false;
    let { lines, fontSize } = horizontal
    if (allowRotation) {
        const vertical = formatTextToLinesOneWay(words, height, width, heightMultiplier, widthMultiplier);
        if (horizontal.fontSize < vertical.fontSize) {
            rotate = true
            lines = vertical.lines
            fontSize = vertical.fontSize
        }
    }


    const translates = [];
    const scale = fontSize / baseFontSize;
    for (const [lineInd, line] of lines.entries()) {
        const lineDispInd = lineInd - lines.length + 1;
        const lineBaseX = leftAligned ? 0 : - lineLen(line.words) * widthMultiplier * baseFontSize / 2
        let wordStartInd = 0
        for (const word of line.words) {
            const y = lineDispInd * heightMultiplier * baseFontSize;
            const x = lineBaseX + wordStartInd * widthMultiplier * baseFontSize;


            translates.push(`translate(${x}px, ${y}px)`);
            wordStartInd += word.length + 1;
        }
    }

    return { translates, scale, rotate }
}


function formatTextToLinesOneWay(words: string[], width: number, height: number, heightMultiplier: number, widthMultiplier: number) {

    let numOfLines = 1;
    const totalLength = lineLen(words)
    let lines = [{ words, length: totalLength }]
    let maxLineLen, widthBasedFontSize, heightBasedFontSize, fontSize: number = 0;
    for (const _ of Array(7)) {
        maxLineLen = lines.reduce((a, b) => Math.max(a, b.length), -Infinity);
        widthBasedFontSize = width / (maxLineLen * widthMultiplier)
        heightBasedFontSize = getDimBasedSize(height, heightMultiplier, numOfLines)
        fontSize = Math.min(widthBasedFontSize, heightBasedFontSize)
        if ((lines.length == words.length) || (fontSize >= getDimBasedSize(height, heightMultiplier, numOfLines + 1))) {
            return { lines, fontSize }
        }
        lines = splitToLines(words, totalLength, numOfLines + 1);
        if (numOfLines == lines.length) {
            break;
        }
        numOfLines = lines.length
    }
    return { lines, fontSize }

}

function splitToLines(words: string[], stringLength: number, numOfLines: number) {
    const lines = [];
    let line = []
    let lineLen = 0
    const maxPossLineLen = (stringLength / numOfLines) * 1.25;
    for (const word of words) {
        // console.log("increasing at", word, lineLen, word.length)
        lineLen += word.length + 1

        if ((lineLen > maxPossLineLen) && (line.length > 0)) {
            // console.log("pushing", line, lineLen)
            lines.push({ words: line, length: lineLen - word.length - 2 })
            line = []
            lineLen = word.length + 1
        }
        line.push(word)
    }
    if (line.length > 0) {
        lines.push({ words: line, length: lineLen - 1 })
    }
    return lines
}

function getDimBasedSize(dimSize: number, dimMultiplier: number, numOfLines: number) {
    return dimSize / (1 + (numOfLines - 1) * dimMultiplier)
}

function lineLen(words: string[]) {
    return words.reduce((x, y) => x + y.length + 1, 0) - 1
}
