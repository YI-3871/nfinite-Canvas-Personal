const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'static', 'index.html'), 'utf8');

test('sidebar removes promotional identity while retaining essential tools', () => {
    const sidebar = html.match(/<aside\b[\s\S]*?<\/aside>/)[0];
    assert.doesNotMatch(sidebar, /github-entry-btn|author-box|social-icon-lite|wuli大雄/);
    assert.doesNotMatch(sidebar, /https?:\/\//);
    for (const id of ['theme-toggle-btn', 'lang-toggle-btn', 'settings-fold-toggle']) {
        assert.ok(sidebar.includes(`id="${id}"`), id);
    }
    for (const page of ['zimage', 'enhance', 'klein', 'angle', 'online', 'gpt-chat',
        'asset-manager', 'api-settings', 'comfyui-settings', 'canvas']) {
        assert.ok(html.includes(`id="frame-${page}"`), page);
    }
});

test('version is display-only and shell has no upstream update request path', () => {
    const badge = html.match(/<div id="project-version-badge"[^>]*>/)[0];
    assert.doesNotMatch(badge, /onclick|onkeydown|tabindex|role="button"/);
    assert.doesNotMatch(html, /id="(?:update-now-btn|project-update-modal)"/);
    assert.doesNotMatch(html, /checkForUpdates|confirmProjectUpdate|rollbackProjectUpdate/);
    assert.doesNotMatch(html, /\/api\/(?:check-update|update-from-github|update-rollback|update-connectivity)/);
    assert.doesNotMatch(html, /hero8152|daniel8152|openProjectPage/);
    assert.match(html, /loadProjectVersion\(\);/);
});

test('every shell inline script remains syntactically valid', () => {
    const scripts = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)];
    assert.ok(scripts.length > 0);
    for (const [index, script] of scripts.entries()) {
        assert.doesNotThrow(() => new vm.Script(script[1], {filename: `index-inline-${index}.js`}));
    }
});

function loadVersionUi(fetch, lang = 'zh') {
    const badge = {
        textContent: 'v-', title: '', children: [],
        replaceChildren() { this.children = []; },
        append(...children) { this.children.push(...children); },
    };
    const context = vm.createContext({
        fetch,
        document: {
            getElementById(id) { return id === 'project-version-badge' ? badge : null; },
            createElement() { return {}; },
        },
        window: {StudioI18n: {lang: () => lang}},
    });
    const start = html.indexOf('        function compactVersion(value) {');
    const end = html.indexOf('</script>', start);
    assert.ok(start >= 0 && end > start);
    vm.runInContext(`let projectVersion = '';\n${html.slice(start, end)}`, context);
    return {context, badge};
}

test('local version is displayed without following upstream metadata', async () => {
    const requests = [];
    const {context, badge} = loadVersionUi(async (url, options) => {
        requests.push({url, options});
        return {ok: true, json: async () => ({
            version: ' 2026.09.10 ',
            version_url: 'https://example.invalid/upstream',
            sources: {github: {version_url: 'https://example.invalid/upstream'}},
        })};
    });
    await context.loadProjectVersion();
    assert.equal(requests.length, 1);
    assert.equal(requests[0].url, '/api/app-info');
    assert.equal(requests[0].options.cache, 'no-store');
    assert.equal(badge.title, '当前版本：v2026.09.10');
    assert.equal(badge.children[0].textContent, 'v09.10');
    assert.equal(badge.children[1].textContent, 'v2026.09.10');
});

test('version label supports English without advertising update checks', async () => {
    const {context, badge} = loadVersionUi(async () => ({
        ok: true, json: async () => ({version: '2026.09.10'}),
    }), 'en');
    await context.loadProjectVersion();
    assert.equal(badge.title, 'Current version: v2026.09.10');
});

test('offline, non-OK and invalid JSON responses do not break the shell', async () => {
    for (const fetch of [
        async () => { throw new Error('offline'); },
        async () => ({ok: false}),
        async () => ({ok: true, json: async () => { throw new Error('invalid JSON'); }}),
    ]) {
        const {context, badge} = loadVersionUi(fetch);
        await assert.doesNotReject(context.loadProjectVersion());
        assert.equal(badge.textContent, 'v-');
    }
});
