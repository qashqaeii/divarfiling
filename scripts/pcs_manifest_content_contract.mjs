/** Native content contract — mirrors pcs-template-scenes / pcs-bindings resolvers (v1). */
export const CONTENT_CONTRACT_VERSION = 1;

export const RESOLVER_DEFINITIONS = {
    poster_headline: {
        engine: 'posterHeadline',
        sources: [
            { origin: 'poster_conf', field: 'headline' },
            { origin: 'property', field: 'headline' },
        ],
        binding_modes: ['linked', 'override', 'detached'],
    },
    overlay_meta_summary: {
        engine: 'overlayMetaSummary',
        property_fields: [
            'location_line',
            'city',
            'property_type',
            'area_label',
            'floor_label',
            'detail_chips',
        ],
        max_parts: 4,
        headline_sources: [
            { origin: 'poster_conf', field: 'headline' },
            { origin: 'property', field: 'headline' },
        ],
        binding_modes: ['linked', 'override', 'detached'],
    },
    pearlescent_meta_lines: {
        engine: 'pearlescentMetaLines',
        feature_source: 'editor_features',
        skip_feature_keys: [
            'location_line',
            'price',
            'deal_mode',
            'file_code',
            'area_label',
            'rooms_label',
        ],
        binding_modes: ['linked', 'override', 'detached'],
    },
    property_deal_badge: {
        engine: 'posterDealBadgeLabel',
        binding: { source: 'property', field: 'deal_mode', mode: 'linked' },
    },
    property_price: {
        binding: { source: 'property', field: 'price', mode: 'linked' },
    },
    brand_contact_footer: {
        binding: { source: 'brand', field: 'contact_footer', mode: 'linked' },
    },
    property_location_line: {
        binding: { source: 'property', field: 'location_line', mode: 'linked' },
    },
};

const LAYER_CONTRACT_BY_ID = {
    'headline-1': 'poster_headline',
    'meta-1': null,
    'location-1': 'property_location_line',
    'deal-1': 'property_deal_badge',
    'price-1': 'property_price',
    'footer-1': 'brand_contact_footer',
};

export function metaResolverForTemplate(templateId) {
    return templateId === 'pearlescent' ? 'pearlescent_meta_lines' : 'overlay_meta_summary';
}

export function buildDynamicContentContract(templateId, scene) {
    const layers = {};
    (scene?.layers || []).forEach((layer) => {
        const id = layer.id;
        let resolverKey = LAYER_CONTRACT_BY_ID[id];
        if (id === 'meta-1') {
            resolverKey = metaResolverForTemplate(templateId);
        }
        if (!resolverKey) return;
        layers[id] = {
            schema_version: CONTENT_CONTRACT_VERSION,
            resolver: resolverKey,
            template_role: layer.templateRole || '',
            layer_type: layer.type,
        };
        if (layer.binding) {
            layers[id].default_binding = layer.binding;
        }
    });
    return {
        schema_version: CONTENT_CONTRACT_VERSION,
        resolvers: RESOLVER_DEFINITIONS,
        layers,
    };
}

export function annotateLayerContentContracts(scene, templateId) {
    if (!scene?.layers) return scene;
    const dynamic = buildDynamicContentContract(templateId, scene);
    scene.layers.forEach((layer) => {
        const spec = dynamic.layers[layer.id];
        if (spec) {
            layer.contentContract = {
                schema_version: CONTENT_CONTRACT_VERSION,
                resolver: spec.resolver,
                template_role: spec.template_role || layer.templateRole || '',
            };
            if (layer.binding) {
                layer.contentContract.default_binding = layer.binding;
            }
        }
    });
    return scene;
}
