/** Sentinel prefix for manifest generation — must not appear in shipped JSON. */
export const MANIFEST_SENTINEL = 'PCS_MANIFEST_';

const SENTINEL_VALUES = [
    `${MANIFEST_SENTINEL}HEADLINE`,
    `${MANIFEST_SENTINEL}LOCATION`,
    `${MANIFEST_SENTINEL}CITY`,
    `${MANIFEST_SENTINEL}HOOD`,
    `${MANIFEST_SENTINEL}TYPE`,
    `${MANIFEST_SENTINEL}AREA`,
    `${MANIFEST_SENTINEL}ROOMS`,
    `${MANIFEST_SENTINEL}FLOOR`,
    `${MANIFEST_SENTINEL}YEAR`,
    `${MANIFEST_SENTINEL}PRICE`,
    `${MANIFEST_SENTINEL}CHIP0`,
    `${MANIFEST_SENTINEL}AM0`,
    `${MANIFEST_SENTINEL}AM1`,
    `${MANIFEST_SENTINEL}CONSULT`,
    `${MANIFEST_SENTINEL}PHONE`,
    `${MANIFEST_SENTINEL}FEAT_AREA`,
    `${MANIFEST_SENTINEL}FEAT_ROOMS`,
];

export function buildManifestGeneratorContext(templateId, formatKey, formats, overlayUrl) {
    const headline = `${MANIFEST_SENTINEL}HEADLINE`;
    return {
        templateId,
        formatKey,
        formats,
        overlayUrl,
        images: ['', '', ''],
        property: {
            headline,
            deal_mode: 'فروش',
            location_line: `${MANIFEST_SENTINEL}LOCATION`,
            city: `${MANIFEST_SENTINEL}CITY`,
            neighborhood: `${MANIFEST_SENTINEL}HOOD`,
            property_type: `${MANIFEST_SENTINEL}TYPE`,
            area_label: `${MANIFEST_SENTINEL}AREA`,
            rooms_label: `${MANIFEST_SENTINEL}ROOMS`,
            floor_label: `${MANIFEST_SENTINEL}FLOOR`,
            build_year_label: `${MANIFEST_SENTINEL}YEAR`,
            price: { show: true, label: `${MANIFEST_SENTINEL}PRICE`, deal_mode: 'فروش' },
            amenities: [`${MANIFEST_SENTINEL}AM0`, `${MANIFEST_SENTINEL}AM1`],
            detail_chips: [`${MANIFEST_SENTINEL}CHIP0`],
        },
        brand: {
            consultant_name: `${MANIFEST_SENTINEL}CONSULT`,
            contact_phone: `${MANIFEST_SENTINEL}PHONE`,
            visibility: {
                consultant_name: true,
                contact_phone: true,
                neighborhood: true,
                price: true,
                area: true,
                bedrooms: true,
                floor: true,
                amenities: true,
                file_code: true,
            },
        },
        features: [
            { key: 'area_label', label: 'متراژ', value: `${MANIFEST_SENTINEL}FEAT_AREA` },
            { key: 'rooms_label', label: 'اتاق', value: `${MANIFEST_SENTINEL}FEAT_ROOMS` },
        ],
        posterConf: {},
    };
}

export function buildManifestGeneratorConf() {
    return {
        headline: `${MANIFEST_SENTINEL}HEADLINE`,
    };
}

function stripSentinels(text) {
    if (typeof text !== 'string' || !text) return '';
    let out = text;
    for (const token of SENTINEL_VALUES) {
        out = out.split(token).join('');
    }
    out = out.split(MANIFEST_SENTINEL).join('');
    return out.replace(/\s·\s·+/g, ' · ').replace(/^\s·\s|\s·\s$/g, '').trim();
}

export function sanitizeManifestScene(scene) {
    if (!scene?.layers) return scene;
    for (const layer of scene.layers) {
        if (layer.type === 'text' || layer.type === 'bound_text') {
            const binding = layer.binding;
            if (binding && binding.mode !== 'detached') {
                layer.text = '';
            } else if (layer.text != null) {
                layer.text = stripSentinels(layer.text);
            }
            if (typeof layer.text === 'string') {
                layer.text = layer.text.replace(/(?:\s·\s)+$/g, '').replace(/^(?:\s·\s)+/g, '').trim();
            }
        }
    }
    return scene;
}

export function assertNoSentinelInManifest(manifest) {
    const raw = JSON.stringify(manifest);
    if (raw.includes(MANIFEST_SENTINEL)) {
        throw new Error(`Sentinel leaked into manifest: ${manifest.template_id}/${manifest.format}`);
    }
}
