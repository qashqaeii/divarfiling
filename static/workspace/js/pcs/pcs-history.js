/**
 * Undo/redo — past holds snapshots *before* each committed change.
 */
(function (global) {
    'use strict';

    function createHistory(maxDepth) {
        return {
            past: [],
            future: [],
            max: maxDepth || 60,
            mergeKey: null,
            lastSnap: null,
        };
    }

    function snapshot(scene) {
        return JSON.stringify(scene);
    }

    /** Call at start of a gesture or before discrete edit; stores current state once. */
    function checkpoint(hist, scene, mergeKey) {
        if (!hist) return;
        const snap = snapshot(scene);
        if (hist.mergeKey && mergeKey && hist.mergeKey === mergeKey) return;
        if (hist.lastSnap === snap) return;
        hist.past.push(snap);
        if (hist.past.length > hist.max) hist.past.shift();
        hist.future = [];
        hist.mergeKey = mergeKey || null;
        hist.lastSnap = snap;
    }

    function pushHistory(hist, scene, mergeKey) {
        checkpoint(hist, scene, mergeKey);
    }

    function endMerge(hist) {
        if (hist) hist.mergeKey = null;
    }

    function undo(hist, currentScene) {
        if (!hist?.past.length) return null;
        hist.future.push(snapshot(currentScene));
        const prev = hist.past.pop();
        hist.lastSnap = prev;
        hist.mergeKey = null;
        return JSON.parse(prev);
    }

    function redo(hist, currentScene) {
        if (!hist?.future.length) return null;
        hist.past.push(snapshot(currentScene));
        const next = hist.future.pop();
        hist.lastSnap = next;
        hist.mergeKey = null;
        return JSON.parse(next);
    }

    global.PCSHistory = {
        createHistory,
        checkpoint,
        pushHistory,
        endMerge,
        undo,
        redo,
    };
}(typeof window !== 'undefined' ? window : globalThis));
