/**
 * Undo/redo for scene documents (per editor session).
 */
(function (global) {
    'use strict';

    function createHistory(maxDepth) {
        return {
            past: [],
            future: [],
            max: maxDepth || 60,
            mergeKey: null,
        };
    }

    function snapshot(scene) {
        return JSON.stringify(scene);
    }

    function pushHistory(hist, scene, mergeKey) {
        if (!hist) return;
        const snap = snapshot(scene);
        if (hist.mergeKey && mergeKey && hist.mergeKey === mergeKey && hist.past.length) {
            hist.past[hist.past.length - 1] = snap;
        } else {
            hist.past.push(snap);
            if (hist.past.length > hist.max) hist.past.shift();
        }
        hist.future = [];
        hist.mergeKey = mergeKey || null;
    }

    function endMerge(hist) {
        if (hist) hist.mergeKey = null;
    }

    function undo(hist, currentScene) {
        if (!hist?.past.length) return null;
        hist.future.push(snapshot(currentScene));
        const prev = hist.past.pop();
        return JSON.parse(prev);
    }

    function redo(hist, currentScene) {
        if (!hist?.future.length) return null;
        hist.past.push(snapshot(currentScene));
        const next = hist.future.pop();
        return JSON.parse(next);
    }

    global.PCSHistory = {
        createHistory,
        pushHistory,
        endMerge,
        undo,
        redo,
    };
}(typeof window !== 'undefined' ? window : globalThis));
