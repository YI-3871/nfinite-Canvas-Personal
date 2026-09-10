const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function loadResultMediaUrls() {
    const canvasSource = fs.readFileSync(
        path.join(__dirname, '..', 'static', 'js', 'canvas.js'),
        'utf8'
    );
    const start = canvasSource.indexOf('function resultMediaUrls(result)');
    const end = canvasSource.indexOf('function ltxDirectorSyncSeconds', start);
    assert.notEqual(start, -1, 'resultMediaUrls must exist in canvas.js');
    assert.notEqual(end, -1, 'resultMediaUrls extraction boundary must exist');

    const context = {
        outputUrlValue(item) {
            return typeof item === 'string' ? item : item?.url || '';
        },
    };
    vm.createContext(context);
    vm.runInContext(canvasSource.slice(start, end), context);
    return context.resultMediaUrls;
}

test('classic canvas accepts image_items arrays returned by background tasks', () => {
    const resultMediaUrls = loadResultMediaUrls();
    const imageItem = {
        url: '/assets/output/online_result_colorfix.png',
        raw_url: '/assets/output/online_result.png',
        trace_id: 'trace_regression',
        color_preservation: {status: 'corrected'},
    };

    const images = resultMediaUrls([imageItem]);

    assert.equal(images.length, 1);
    assert.equal(images[0].url, imageItem.url);
    assert.equal(images[0].raw_url, imageItem.raw_url);
    assert.equal(images[0].trace_id, imageItem.trace_id);
    assert.deepEqual(images[0].color_preservation, imageItem.color_preservation);
});

test('classic canvas accepts string arrays and deduplicates a full API result', () => {
    const resultMediaUrls = loadResultMediaUrls();
    const url = '/assets/output/online_result.png';

    const stringImages = resultMediaUrls([url]);
    assert.equal(stringImages.length, 1);
    assert.equal(stringImages[0], url);

    const images = resultMediaUrls({
        images: [url],
        raw_images: [url],
        image_items: [{url, raw_url: url, trace_id: 'trace_regression'}],
    });
    assert.equal(images.length, 1);
    assert.equal(images[0].url, url);
    assert.equal(images[0].trace_id, 'trace_regression');
});

test('parsed API image items are persisted on the classic OUTPUT node', () => {
    const resultMediaUrls = loadResultMediaUrls();
    const canvasSource = fs.readFileSync(
        path.join(__dirname, '..', 'static', 'js', 'canvas.js'),
        'utf8'
    );
    const start = canvasSource.indexOf('function appendOutputImages(out, images, compareRef, metas=[], layout=null)');
    const end = canvasSource.indexOf('function outputCompareUrlFor', start);
    assert.notEqual(start, -1, 'appendOutputImages must exist in canvas.js');
    assert.notEqual(end, -1, 'appendOutputImages extraction boundary must exist');

    const context = {
        outputUrlValue(item) {
            return typeof item === 'string' ? item : item?.url || '';
        },
    };
    vm.createContext(context);
    vm.runInContext(canvasSource.slice(start, end), context);

    const result = {
        images: ['/assets/output/online_result_colorfix.png'],
        raw_images: ['/assets/output/online_result.png'],
        image_items: [{
            url: '/assets/output/online_result_colorfix.png',
            raw_url: '/assets/output/online_result.png',
            trace_id: 'trace_regression',
            color_preservation: {status: 'corrected'},
        }],
    };
    const outputNode = {type: 'output', images: []};
    const images = resultMediaUrls(result);

    context.appendOutputImages(outputNode, images, null, [{runMs: 42, run: {}}]);

    assert.equal(outputNode.images.length, 1);
    assert.equal(outputNode.images[0].url, result.images[0]);
    assert.equal(outputNode.images[0].raw_url, result.raw_images[0]);
    assert.equal(outputNode.images[0].trace_id, 'trace_regression');
    assert.equal(outputNode.images[0].color_preservation.status, 'corrected');
});
