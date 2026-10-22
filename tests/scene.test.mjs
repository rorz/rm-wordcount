import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { textPayload, pageText, readTextItems, orderedText, MAX_FILE_BYTES } from '../src/scene.mjs';
import { countWords } from '../src/wordcount.mjs';

const fixture = name => readFileSync(new URL('./fixtures/' + name, import.meta.url));
const header = Buffer.from('reMarkable .lines file, version=6          ');
const u32 = n => { const b = Buffer.alloc(4); b.writeUInt32LE(n); return b; };
const varuint = n => {
    const bytes = [];
    do { bytes.push((n % 128) | (n >= 128 ? 128 : 0)); n = Math.floor(n / 128); } while (n);
    return Buffer.from(bytes);
};
const block = (type, body, minimum = 1) => Buffer.concat([u32(body.length), Buffer.from([0, minimum, minimum, type]), body]);
const sub = (tag, body) => Buffer.concat([Buffer.from([tag * 16 + 12]), u32(body.length), body]);
const id = (tag, a, b) => Buffer.concat([Buffer.from([tag * 16 + 15, a]), varuint(b)]);
const node = (n, text, left = [0, 0], right = [0, 0], extra = {}) => ({id: n, text, left, right, deleted: 0, format: false, ...extra});

for (const [file, expected, count] of [
    ['Normal_AB.rm', 'AB', 1],
    ['Bold_Heading_Bullet_Normal.rm', 'A\nnew line\nB is a letter of the alphabet\nC', 11],
    ['Normal_A_stroke_2_layers_v3.3.2.rm', 'A\nv3.2.2\nNormal bold italic\nBold italic normal\nBold line\nNormal line\nHeading line', 14],
    ['test-crdt-ordering.rm', 'A12_Z', 2],
    ['Wikipedia_highlighted_p1.rm', '', 0],
]) {
    test(`real notebook: ${file}`, () => {
        const text = pageText(textPayload(fixture(file)));
        assert.equal(text, expected);
        assert.equal(countWords(text), count);
    });
}

test('insertions inside an existing chunk are ordered before counting', () => {
    assert.equal(orderedText([node([1, 1], 'helloworld'), node([2, 1], ' ', [1, 5], [1, 6])]), 'hello world');
});
test('deleted characters preserve ordering but do not add words', () => {
    const text = orderedText([
        node([1, 1], 'one ', [0, 0], [1, 5]),
        node([1, 5], '', [1, 4], [1, 9], { deleted: 4 }),
        node([1, 9], 'three', [1, 8]),
    ]);
    assert.equal(text, 'one three');
});
test('format markers do not split a word', () => {
    assert.equal(orderedText([
        node([1, 1], 'hel', [0, 0], [1, 4]),
        node([1, 4], '', [1, 3], [1, 5], { format: true }),
        node([1, 5], 'lo', [1, 4]),
    ]), 'hello');
});
test('concurrent authors are ordered by descending author then ascending clock', () => {
    assert.equal(orderedText([node([1, 1], 'low'), node([2, 1], 'high')]), 'highlow');
});
test('surrogate pairs use one CRDT position', () => {
    assert.equal(orderedText([node([1, 1], 'a🙂z'), node([2, 1], ' ', [1, 2], [1, 3])]), 'a🙂 z');
});
test('cycles fail instead of producing a partial count', () => {
    assert.throws(() => orderedText([node([1, 1], 'a', [1, 2]), node([1, 2], 'b', [1, 1])]), /Cyclic/);
});
test('huge deletion runs are bounded', () => {
    assert.throws(() => orderedText([node([1, 1], '', [0, 0], [0, 0], { deleted: 0xffffffff })]), /limit/);
});
test('incomplete saves and wrong formats never look like zero words', () => {
    const full = fixture('Normal_AB.rm');
    for (const length of [0, 4, 42, full.length - 1]) assert.throws(() => textPayload(full.subarray(0, length)));
    assert.throws(() => textPayload(Buffer.alloc(50)), /format/);
    assert.throws(() => textPayload(Buffer.alloc(MAX_FILE_BYTES + 1)), /limit/);
});
test('unknown non-text blocks are skipped, future text formats rejected', () => {
    assert.deepEqual(textPayload(Buffer.concat([header, block(222, Buffer.from('ignored'))])), []);
    assert.throws(() => textPayload(Buffer.concat([header, block(7, Buffer.from('future'), 2)])), /version/);
});
test('a trailing truncated ink block invalidates the whole saved page', () => {
    assert.throws(() => textPayload(Buffer.concat([fixture('Normal_AB.rm'), u32(100)])), /Incomplete/);
});
test('last root-text block wins, like rmscene', () => {
    const first = fixture('Normal_AB.rm');
    const last = fixture('Bold_Heading_Bullet_Normal.rm');
    assert.equal(countWords(pageText(textPayload(Buffer.concat([first, last.subarray(header.length)])))), 11);
});

function itemsFile(items) {
    const encoded = items.map(item => {
        const utf8 = Buffer.from(item.text);
        const string = sub(6, Buffer.concat([
            varuint(utf8.length), Buffer.from([1]), utf8,
            item.format ? Buffer.concat([Buffer.from([0x24]), u32(1)]) : Buffer.alloc(0),
        ]));
        return sub(0, Buffer.concat([
            id(2, ...item.id), id(3, ...item.left), id(4, ...item.right), Buffer.from([0x54]), u32(item.deleted), string,
        ]));
    });
    const body = Buffer.concat([
        id(1, 0, 0), sub(2, Buffer.concat([sub(1, sub(1, Buffer.concat([varuint(items.length), ...encoded]))), sub(2, sub(1, Buffer.from([0])))])),
        sub(3, Buffer.alloc(16)), Buffer.from([0x44]), Buffer.alloc(4),
    ]);
    return Buffer.concat([header, block(7, body)]);
}
const textFile = utf8 => itemsFile([node([1, 1], utf8)]);

test('repeated item IDs replace values without changing their insertion order', () => {
    const payload = textPayload(itemsFile([
        node([1, 1], 'old'), node([1, 4], ' words', [1, 3]), node([1, 1], 'new'),
    ]));
    assert.deepEqual(readTextItems(payload).map(item => item.text), ['new', ' words']);
    assert.equal(pageText(payload), 'new words');
});
test('overlapping character IDs respect later edits and deletion tombstones', () => {
    assert.equal(orderedText([
        node([1, 1], 'one two three'),
        node([1, 5], '', [1, 4], [1, 9], { deleted: 4 }),
        node([2, 1], 'four ', [1, 4], [1, 5]),
    ]), 'one four three');
});
test('2000-word page: append, delete and undo with fragmented edit history', () => {
    const original = 'ordinary '.repeat(2000).trimEnd();
    const history = [node([1, 1], original)];
    const check = expected => {
        const text = pageText(textPayload(itemsFile(history)));
        assert.equal(text, expected);
        assert.equal(countWords(text), expected.trim().split(/\s+/u).length);
    };
    check(original);
    history.push(node([2, 1], ' four five six', [1, original.length]));
    check(original + ' four five six');
    // Split the original chunk, deleting its second word. The first item's
    // replacement retains its position before the remaining split chunk.
    history.push(node([1, 1], 'ordinary ', [0, 0], [1, 10]));
    history.push(node([1, 10], '', [1, 9], [1, 19], { deleted: 9 }));
    history.push(node([1, 19], original.slice(18), [1, 18]));
    check(original.slice(9) + ' four five six');
    history.push(node([2, 1], '', [1, original.length], [0, 0], { deleted: 14 }));
    check(original.slice(9));
});
test('UTF-8 across scripts and supplementary characters', () => {
    const text = 'café Привет مرحبا 你好 🙂 𐐀';
    assert.equal(pageText(textPayload(textFile(Buffer.from(text)))), text);
});
test('malformed UTF-8 fails closed', () => {
    for (const bytes of [[0xc0, 0x80], [0xed, 0xa0, 0x80], [0xf4, 0x90, 0x80, 0x80], [0xe2, 0x82]]) {
        assert.throws(() => pageText(textPayload(textFile(Buffer.from(bytes)))), /encoding/);
    }
});
