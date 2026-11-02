#!/usr/bin/env node
/**
 * Generate static PCS template manifests from the same JS modules as the web studio.
 *
 * Regenerate when pcs-template-scenes.js, pcs-schema.js, or overlay assets change:
 *   node scripts/generate_pcs_manifests.mjs
 */
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';
import { extractImageSlotMetadata } from './pcs_manifest_enrich.mjs';
import {
    assertNoSentinelInManifest,
    buildManifestGeneratorConf,
    buildManifestGeneratorContext,
    sanitizeManifestScene,
} from './pcs_manifest_sanitize.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
const PCS_DIR = path.join(ROOT, 'static', 'workspace', 'js', 'pcs');
const OUT_DIR = path.join(ROOT, 'static', 'workspace', 'pcs', 'manifests');

const TEMPLATE_IDS = [
    'pearlescent',
    'pearlescent_ribbon',
    'sculptural',
    'sculpted_travertine',
    'emerald_atelier',
    'pearl_gallery',
    'burgundy_alabaster',
    'amethyst_ceramic',
    'champagne_origami',
    'glacier_prism',
    'mediterranean_papercut',
    'terracotta_terrace',
    'brutalist_concrete',
];

const FORMATS = {
    story: { width: 1080, height: 1920, aspect: '9/16' },
    post: { width: 1080, height: 1350, aspect: '4/5' },
    square: { width: 1080, height: 1080, aspect: '1/1' },
};

const OVERLAY_BY_TEMPLATE = {
    pearlescent: 'images/Pearlescent Blue Real Estate Story Template-3.webp',
    pearlescent_ribbon: 'images/Pearlescent ribbon luxury real estate template-4.png',
    sculptural: 'images/Sculptural ivory olive real estate story template-4.webp',
    sculpted_travertine: 'images/Sculpted travertine luxury story template.png',
    emerald_atelier: 'images/Emerald Atelier architectural story template-3.webp',
    pearl_gallery: 'images/Pearl Gallery luxury property story-2.webp',
    burgundy_alabaster: 'images/Burgundy Alabaster Gallery Story Template-5.webp',
    amethyst_ceramic: 'images/Amethyst Ceramic Luxury Property Story Template-4.webp',
    champagne_origami: 'images/Champagne Origami Luxury Estate Story-5.webp',
    glacier_prism: 'images/Glacier prism luxury property story-1.webp',
    mediterranean_papercut: 'images/Mediterranean paper-cut property story template-3.webp',
    terracotta_terrace: 'images/Persian Real Estate Content Studio Dashboard.webp',
    brutalist_concrete: 'images/Brutalist red-and-concrete real estate template-4.webp',
};

const SOURCE_FILES = [
    'pcs-schema.js',
    'pcs-template-scenes.js',
    'pcs-assets.js',
    'pcs-bindings.js',
];

function sha256File(filePath) {
    const buf = fs.readFileSync(filePath);
    return crypto.createHash('sha256').update(buf).digest('hex');
}

function loadPcsSandbox() {
    const sandbox = {
        window: {},
        globalThis: {},
        console,
        Math,
        JSON,
        parseInt,
        parseFloat,
        isNaN,
        isFinite,
        Number,
        String,
        Array,
        Object,
        Set,
    };
    sandbox.window = sandbox;
    sandbox.globalThis = sandbox;
    for (const name of SOURCE_FILES) {
        const code = fs.readFileSync(path.join(PCS_DIR, name), 'utf8');
        vm.runInNewContext(code, sandbox, { filename: name });
    }
    return sandbox;
}

function main() {
    const sandbox = loadPcsSandbox();
    const Schema = sandbox.PCSSchema;
    const Scenes = sandbox.PCSTemplateScenes;
    const Assets = sandbox.PCSAssets;
    if (!Schema || !Scenes) {
        console.error('Failed to load PCS JS modules');
        process.exit(1);
    }

    const source_hashes = {};
    for (const name of SOURCE_FILES) {
        source_hashes[name] = sha256File(path.join(PCS_DIR, name));
    }
    const revisionPayload = JSON.stringify(source_hashes);
    const layout_revision = crypto.createHash('sha256').update(revisionPayload).digest('hex').slice(0, 16);
    const manifest_version = `pcs-manifest-${layout_revision}`;

    fs.mkdirSync(OUT_DIR, { recursive: true });

    const index = {
        manifest_version,
        layout_revision,
        schema_version: 2,
        source_hashes,
        templates: TEMPLATE_IDS,
        formats: Object.keys(FORMATS),
        generated_at: new Date().toISOString(),
        entries: [],
    };

    for (const templateId of TEMPLATE_IDS) {
        const templateDir = path.join(OUT_DIR, templateId);
        fs.mkdirSync(templateDir, { recursive: true });
        const overlayRel = OVERLAY_BY_TEMPLATE[templateId];
        for (const [formatKey, fmt] of Object.entries(FORMATS)) {
            const ctx = buildManifestGeneratorContext(
                templateId,
                formatKey,
                FORMATS,
                `/static/${overlayRel}`,
            );
            const conf = buildManifestGeneratorConf();
            const baseScene = Schema.emptyScene(templateId, formatKey, FORMATS);
            let scene = Scenes.buildInitialScene(conf, ctx, baseScene);
            scene = Scenes.normalizeSceneLayerOrder(scene);
            scene = sanitizeManifestScene(scene);
            scene = Schema.normalizeScene(scene, templateId, formatKey, FORMATS);

            const w = scene.canvas.width;
            const h = scene.canvas.height;
            const boxes = Scenes.storyBoxes(templateId, w, h);
            const background = Scenes.overlayCanvasBackground(templateId) || '';
            const slotMeta = extractImageSlotMetadata(scene, boxes);
            const manifest = {
                template_id: templateId,
                schema_version: 2,
                manifest_version,
                layout_revision,
                format: formatKey,
                canvas: {
                    width: fmt.width,
                    height: fmt.height,
                },
                overlay_path: overlayRel,
                overlay_asset_ref: Assets.templateAssetId(templateId),
                background,
                scene,
                image_slots: slotMeta.image_slots,
                layout_calibration: slotMeta.layout_calibration,
            };

            assertNoSentinelInManifest(manifest);

            const outPath = path.join(templateDir, `${formatKey}.json`);
            fs.writeFileSync(outPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
            index.entries.push({ template_id: templateId, format: formatKey, path: `manifests/${templateId}/${formatKey}.json` });
        }
    }

    fs.writeFileSync(path.join(OUT_DIR, 'index.json'), `${JSON.stringify(index, null, 2)}\n`, 'utf8');
    console.log(`Generated ${index.entries.length} manifests → ${OUT_DIR}`);
    console.log(`manifest_version=${manifest_version}`);
}

main();
