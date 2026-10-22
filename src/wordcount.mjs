// SPDX-License-Identifier: GPL-3.0-only
import { category } from './unicode.mjs';

// Letters/numbers start words; combining marks and joiners extend them.
// Apostrophes and hyphens inside words stay in the same word. En/em dashes
// separate words. Decimal separators between numbers stay in the same word.
export function countWords(text) {
    const chars = Array.from(text);
    let count = 0;
    let inWord = false;
    let previous = 0;
    for (let i = 0; i < chars.length; i++) {
        const cp = chars[i].codePointAt(0);
        const kind = category(cp);
        if (kind === 1 || kind === 2) {
            if (!inWord) count++;
            inWord = true;
        } else if (kind === 3 || cp === 0x200c || cp === 0x200d) {
            // A mark alone isn't a word.
        } else {
            const next = i + 1 < chars.length ? category(chars[i + 1].codePointAt(0)) : 0;
            const connector = cp === 0x27 || cp === 0x2019 || cp === 0x2d || cp === 0x2010 || cp === 0x2011;
            const decimal = (cp === 0x2e || cp === 0x2c) && previous === 2 && next === 2;
            inWord = inWord && (decimal || (connector && (next === 1 || next === 2)));
        }
        previous = kind;
    }
    return count;
}
