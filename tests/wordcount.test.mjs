import test from 'node:test';
import assert from 'node:assert/strict';
import { countWords } from '../src/wordcount.mjs';

for (const [text, count] of [
    ['', 0], [' \n\t\u00a0', 0], ['Hello, world!', 2], ['... — ! 🙂 🎉', 0],
    ["Don't stop believing", 3], ['It’s a well-written note', 4],
    ['one—two – three', 3], ['one/two three_four', 4], ['123 3.14 1,000 v3.2.2', 4],
    ['“quoted words”', 2], ['café cafe\u0301 naïve', 3], ['\u0301 alone', 1],
    ['Привет мир مرحبا بالعالم', 4], ['नमस्ते दुनिया', 2], ['你好 世界', 2],
    ['first\u00a0second\u2028third\u2029fourth', 4], ['𐐀𐐁 𝟙𝟚', 2],
    ['hello🙂world', 2], ['one\u200btwo', 2], ["' -- ’", 0],
]) {
    test(`count ${JSON.stringify(text)}`, () => assert.equal(countWords(text), count));
}

test('long page', () => assert.equal(countWords('A well-written sentence.\n'.repeat(10000)), 30000));
