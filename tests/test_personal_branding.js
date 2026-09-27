const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const repository = 'https://github.com/YI-3871/nfinite-Canvas-Personal';

test('personal documentation replaces old identity, screenshots and donation content', () => {
    for (const file of ['README.md', 'LICENSE', '运行说明.txt']) {
        const text = read(file);
        assert.ok(text.includes(repository), file);
        assert.doesNotMatch(text, /hero8152|wuli大雄|大雄画布|user-attachments|赞赏|打赏|[?&](?:aff|inviteCode)=/i);
    }
    assert.match(read('README.md'), /Nano Banana 2.*多轮/);
    assert.match(read('LICENSE'), /商业使用须另行取得授权/);
    assert.match(read('LICENSE'), /Third-party components/);
    assert.equal(fs.existsSync(path.join(root, '赞赏.png')), false);
});

test('plugin presentation names and project links use the personal identity', () => {
    for (const file of [
        'tools/chrome-local-asset-importer/popup.html',
        'tools/chrome-local-asset-importer/sidepanel.html',
        'tools/photoshop-asset-connector/index.html',
    ]) {
        const text = read(file);
        assert.match(text, /YI 画布工具/);
        assert.doesNotMatch(text, /大雄画布|>DX<|hero8152/);
    }
    for (const file of [
        'tools/chrome-local-asset-importer/popup.js',
        'tools/photoshop-asset-connector/js/app.js',
    ]) {
        const text = read(file);
        assert.ok(text.includes(repository), file);
        assert.doesNotMatch(text, /github\.com\/hero8152/);
        assert.doesNotThrow(() => new vm.Script(text, {filename: file}));
    }
});

test('plugin identity and existing settings keys are preserved for compatibility', () => {
    const manifest = JSON.parse(read('tools/photoshop-asset-connector/manifest.json'));
    assert.equal(manifest.id, 'com.daxiong.canvas.assets');
    assert.equal(manifest.name, 'YI 画布工具');
    assert.equal(manifest.entrypoints[0].label, 'YI 画布工具');
    assert.match(read('tools/photoshop-asset-connector/js/state.js'), /daxiong\./);
    assert.match(read('tools/photoshop-asset-connector/js/app.js'), /DX/);
    assert.equal(JSON.parse(read('tools/chrome-local-asset-importer/manifest.json')).manifest_version, 3);
});

test('registration links and onboarding docs contain no old referral or video links', () => {
    for (const file of ['static/api-settings.html', '新手运行与使用教程.md', '运行说明.txt']) {
        assert.doesNotMatch(read(file), /[?&](?:aff|inviteCode)=|BV1qvLj67Euh|BV1xAVT6hEBk/i);
    }
    assert.match(read('static/api-settings.html'), /https:\/\/www\.runninghub\.cn\/enterprise-api\/consumerApi/);
});

test('real model resource identifiers are not renamed as branding', () => {
    assert.match(read('main.py'), /Daniel8152\//);
    assert.match(read('static/klein.html'), /Daniel8152\/Klein-enhance/);
});
