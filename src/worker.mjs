// SPDX-License-Identifier: GPL-3.0-only
import { pageText } from './scene.mjs';
import { countWords } from './wordcount.mjs';

WorkerScript.onMessage = function(message) {
    try {
        const count = countWords(pageText(message.payload));
        WorkerScript.sendMessage({ generation: message.generation, count: count, error: '' });
    } catch (error) {
        WorkerScript.sendMessage({ generation: message.generation, count: -1, error: String(error.message) });
    }
};
