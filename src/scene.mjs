// SPDX-License-Identifier: GPL-3.0-only
// The v6 format and CRDT ordering follow rmscene (MIT); see THIRD_PARTY.md.
const HEADER = 'reMarkable .lines file, version=6          ';
export const MAX_FILE_BYTES = 32 * 1024 * 1024;
const MAX_TEXT_BYTES = 2 * 1024 * 1024;
const MAX_ITEMS = 250000;

class Reader {
    constructor(bytes, start = 0, end = bytes.length) {
        this.bytes = bytes;
        this.pos = start;
        this.end = end;
    }
    need(size) {
        if (!Number.isSafeInteger(size) || size < 0 || this.pos + size > this.end)
            throw new Error('Incomplete page data');
    }
    byte() { this.need(1); return this.bytes[this.pos++]; }
    uint32() {
        this.need(4);
        const p = this.pos;
        this.pos += 4;
        return this.bytes[p] + this.bytes[p + 1] * 256 + this.bytes[p + 2] * 65536 + this.bytes[p + 3] * 16777216;
    }
    varuint() {
        let value = 0;
        let factor = 1;
        for (let i = 0; i < 8; i++) {
            const b = this.byte();
            value += (b & 127) * factor;
            if (!Number.isSafeInteger(value)) throw new Error('Invalid integer');
            if (b < 128) return value;
            factor *= 128;
        }
        throw new Error('Invalid integer');
    }
    tag(index, type) {
        if (this.varuint() !== index * 16 + type) throw new Error('Unsupported text structure');
    }
    id(index) { this.tag(index, 15); return [this.byte(), this.varuint()]; }
    sub(index) {
        this.tag(index, 12);
        const size = this.uint32();
        this.need(size);
        const result = new Reader(this.bytes, this.pos, this.pos + size);
        this.pos += size;
        return result;
    }
}

// Scan framing on the UI thread; ignore ink/images without decoding them.
// Only the small root-text block is copied to the worker. Validate the entire
// file first so an in-progress save never produces a plausible partial count.
export function textPayload(buffer) {
    const bytes = new Uint8Array(buffer);
    if (bytes.length > MAX_FILE_BYTES) throw new Error('Page exceeds the size limit');
    if (bytes.length < HEADER.length) throw new Error('Incomplete page data');
    for (let i = 0; i < HEADER.length; i++) {
        if (bytes[i] !== HEADER.charCodeAt(i)) throw new Error('Unsupported page format');
    }
    const r = new Reader(bytes, HEADER.length);
    let payload = null;
    while (r.pos < r.end) {
        const size = r.uint32();
        const reserved = r.byte();
        const minimum = r.byte();
        const current = r.byte();
        const type = r.byte();
        if (reserved !== 0 || minimum > current) throw new Error('Invalid page block');
        r.need(size);
        if (type === 7) {
            if (minimum > 1) throw new Error('Unsupported text version');
            if (size > MAX_TEXT_BYTES) throw new Error('Text exceeds the size limit');
            payload = bytes.subarray(r.pos, r.pos + size);
        }
        r.pos += size;
    }
    // Ordinary arrays are supported by WorkerScript message serialization.
    return payload === null ? [] : Array.from(payload);
}

function utf8(r, length) {
    r.need(length);
    const end = r.pos + length;
    const chars = [];
    while (r.pos < end) {
        let cp = r.byte();
        if (cp < 128) { chars.push(String.fromCharCode(cp)); continue; }
        let count, minimum;
        if (cp >= 0xc2 && cp <= 0xdf) { count = 1; minimum = 0x80; cp &= 31; }
        else if (cp >= 0xe0 && cp <= 0xef) { count = 2; minimum = 0x800; cp &= 15; }
        else if (cp >= 0xf0 && cp <= 0xf4) { count = 3; minimum = 0x10000; cp &= 7; }
        else throw new Error('Invalid text encoding');
        if (r.pos + count > end) throw new Error('Incomplete text encoding');
        for (let i = 0; i < count; i++) {
            const b = r.byte();
            if ((b & 0xc0) !== 0x80) throw new Error('Invalid text encoding');
            cp = cp * 64 + (b & 63);
        }
        if (cp < minimum || cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff)) throw new Error('Invalid text encoding');
        chars.push(String.fromCodePoint(cp));
    }
    return chars.join('');
}

const key = id => id[0] + ':' + id[1];
const terminal = id => id[0] === 0 && id[1] === 0;

export function readTextItems(payload) {
    if (payload.length === 0) return [];
    const r = new Reader(payload);
    if (!terminal(r.id(1))) throw new Error('Unsupported text root');
    const value = r.sub(2);
    const items = value.sub(1).sub(1);
    const count = items.varuint();
    if (count > MAX_ITEMS) throw new Error('Too many text items');
    const result = [];
    const positions = Object.create(null);
    for (let i = 0; i < count; i++) {
        const item = items.sub(0);
        const id = item.id(2);
        const left = item.id(3);
        const right = item.id(4);
        item.tag(5, 4);
        const deleted = item.uint32();
        let text = '';
        let format = false;
        if (item.pos < item.end) {
            const string = item.sub(6);
            const length = string.varuint();
            if (string.byte() !== 1) throw new Error('Unsupported text encoding');
            text = utf8(string, length);
            if (string.pos < string.end) {
                string.tag(2, 4);
                string.uint32();
                if (text !== '') throw new Error('Unsupported inline formatting');
                format = true;
            }
            if (string.pos !== string.end) throw new Error('Unsupported string fields');
        }
        if (item.pos !== item.end || (deleted && text)) throw new Error('Unsupported text item');
        if (terminal(id)) throw new Error('Invalid text identifier');
        const name = key(id);
        let position = positions[name];
        if (position === undefined) {
            position = result.length;
            positions[name] = position;
        }
        result[position] = { id, left, right, deleted, text, format };
    }
    if (items.pos !== items.end) throw new Error('Unsupported text items');
    // Validate the remaining required containers without interpreting styling.
    value.sub(2);
    r.sub(3);
    r.tag(4, 4);
    r.uint32();
    return result;
}

// Reconstruct the edited text, including tombstone positions and formatting
// markers. Concatenating stored strings would count deleted/reordered words.
export function orderedText(items) {
    // Qt's JS Map scans its entries on lookup. Use a string-keyed dictionary
    // so expanding and linking a long page does not become quadratic.
    const nodes = Object.create(null);
    const names = [];
    let total = 0;
    for (const item of items) {
        const chars = item.deleted ? null : Array.from(item.text);
        const length = item.deleted || (item.format ? 1 : chars.length);
        total += length;
        if (total > MAX_ITEMS || !Number.isSafeInteger(item.id[1] + length)) throw new Error('Text exceeds the item limit');
        for (let i = 0; i < length; i++) {
            const id = [item.id[0], item.id[1] + i];
            const left = i === 0 ? item.left : [id[0], id[1] - 1];
            const right = i === length - 1 ? item.right : [id[0], id[1] + 1];
            const name = key(id);
            if (nodes[name] === undefined) names.push(name);
            nodes[name] = { id, left, right, text: item.deleted || item.format ? '' : chars[i], degree: 0, next: [] };
        }
    }
    function edge(from, to) { from.next.push(to); to.degree++; }
    for (const name of names) {
        const node = nodes[name];
        const left = nodes[key(node.left)];
        const right = nodes[key(node.right)];
        if (left) edge(left, node);
        if (right) edge(node, right);
    }
    // A heap keeps long pages O(n log n) and concurrent edits deterministic.
    const heap = [];
    const before = (a, b) => a.id[0] !== b.id[0] ? a.id[0] > b.id[0] : a.id[1] < b.id[1];
    function push(node) {
        let i = heap.length;
        heap.push(node);
        while (i > 0) {
            const parent = (i - 1) >> 1;
            if (!before(node, heap[parent])) break;
            heap[i] = heap[parent]; i = parent;
        }
        heap[i] = node;
    }
    function pop() {
        const result = heap[0];
        const tail = heap.pop();
        if (heap.length) {
            let i = 0;
            while (2 * i + 1 < heap.length) {
                let child = 2 * i + 1;
                if (child + 1 < heap.length && before(heap[child + 1], heap[child])) child++;
                if (!before(heap[child], tail)) break;
                heap[i] = heap[child]; i = child;
            }
            heap[i] = tail;
        }
        return result;
    }
    for (const name of names) if (nodes[name].degree === 0) push(nodes[name]);
    const output = [];
    let visited = 0;
    while (heap.length) {
        const node = pop();
        output.push(node.text); visited++;
        for (const next of node.next) if (--next.degree === 0) push(next);
    }
    if (visited !== names.length) throw new Error('Cyclic text sequence');
    return output.join('');
}

export function pageText(payload) { return orderedText(readTextItems(payload)); }
