const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'static/js/api-settings.js'), 'utf8');
const translations = fs.readFileSync(path.join(root, 'static/js/i18n/api-settings.js'), 'utf8');

// Evaluate configuration only: no page initialization, requests or user settings.
function readRecommendedConfig() {
    const start = source.indexOf('const VOLCENGINE_DEFAULT_BASE_URL =');
    const end = source.indexOf('const RECOMMEND_GROUPS =', start);
    assert.ok(start >= 0 && end > start, 'configuration extraction boundaries exist');
    const json = vm.runInNewContext(`${source.slice(start, end)}\n` +
        'JSON.stringify({apis: RECOMMENDED_APIS, guides: ONBOARDING_GUIDES})');
    return JSON.parse(json);
}

test('API settings contain no private promotion or referral parameters', () => {
    for (const text of [source, translations]) {
        assert.doesNotMatch(text, /recommendSeedancePrivate|recommend-seedance-private/);
        assert.doesNotMatch(text, /space\.bilibili\.com\/78652351|B站私信/);
        assert.doesNotMatch(text, /[?&](?:aff|inviteCode)=/i);
        assert.doesNotMatch(text, /专属注册链接|六折专属优惠|dedicated 40% off registration link/i);
    }
});

test('API settings and translations remain syntactically valid', () => {
    assert.doesNotThrow(() => new vm.Script(source, {filename: 'api-settings.js'}));
    assert.doesNotThrow(() => new vm.Script(translations, {filename: 'i18n/api-settings.js'}));
});

test('recommended provider order, service addresses and request modes remain unchanged', () => {
    const {apis} = readRecommendedConfig();
    assert.deepEqual(apis.map(api => [api.name, api.base_url, api.protocol, api.image_request_mode || '']), [
        ['EXELLOME', 'https://new.exellome.online', 'apimart', 'openai-video-proxy'],
        ['FHL', 'https://www.fhl.mom', 'openai', 'openai-responses'],
        ['VIP-GPT', 'https://www.vip-gpt.net', 'openai', ''],
        ['RunningHub', 'https://www.runninghub.cn', 'runninghub', 'openai'],
        ['APIMART', 'https://api.apimart.ai', 'apimart', ''],
        ['灵境API', 'https://apistudio.vip', 'openai', ''],
        ['ModelScope', 'https://api-inference.modelscope.cn/v1', 'openai', 'openai'],
        ['Agnes AI', 'https://apihub.agnes-ai.com', 'openai', 'openai-json'],
    ]);
});

test('registration and wallet links retain their destination without referral attribution', () => {
    const {apis, guides} = readRecommendedConfig();
    assert.deepEqual(apis.map(api => [api.register_url, api.register_url_cn || '']), [
        ['https://new.exellome.online/register', ''],
        ['https://www.fhl.mom/register', ''],
        ['https://www.vip-gpt.net/vip-gpt/register', ''],
        ['https://www.runninghub.ai/enterprise-api/consumerApi', 'https://www.runninghub.cn/enterprise-api/consumerApi'],
        ['https://apimart.ai/zh/register', 'https://apib.ai/register'],
        ['https://apistudio.vip/register', ''],
        ['https://www.modelscope.ai/my/access/token', 'https://www.modelscope.cn/my/access/token'],
        ['https://platform.agnes-ai.com/settings/apiKeys', ''],
    ]);
    assert.equal(guides.runninghub.walletPrimaryUrl, 'https://www.runninghub.cn/enterprise-api/sharedApi');
    assert.equal(guides.runninghub.walletSecondaryUrl, 'https://www.runninghub.ai/enterprise-api/sharedApi');
});

test('model presets and model-specific protocols remain unchanged', () => {
    const {apis} = readRecommendedConfig();
    assert.deepEqual(apis.map(api => [api.image_models || [], api.chat_models || [], api.video_models || []]), [
        [['gpt-image2-2k', 'gpt-image2-4k', 'Nano-Banana-2-2k', 'Nano-Banana-2-4k', 'Nano-Banana-Pro-2k', 'Nano-Banana-Pro-4k'], [], []],
        [['gpt-image-2', 'gpt-image-2-2k', 'gpt-image-2-4k', 'nano-banana'], ['gpt-5.5'], []],
        [[], [], []],
        [[], [], []],
        [[], [], []],
        [['gpt-image-2', 'gemini-3.1-flash-image-preview', 'gemini-3-pro-image-preview'], ['gpt-5.5'], ['veo3.1-fast']],
        [[], [], []],
        [['agnes-image-2.1-flash', 'agnes-image-2.0-flash'], [], ['agnes-video-v2.0']],
    ]);
    assert.equal(apis[2].empty_models_on_save, true);
    assert.deepEqual(apis[5].model_protocols, {
        'gemini-3.1-flash-image-preview': 'gemini',
        'gemini-3-pro-image-preview': 'gemini',
    });
});
