import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { createMediaPlugins, POSTS_DIR, readManifest } from './media.mjs';

const slug = 'plog_202607-202610';
const vfile = { path: path.join(POSTS_DIR, slug, 'index.md') };
const dimensions = readManifest()[`${slug}/image-1.png`];

for (const dev of [false, true]) {
  test(`${dev ? 'development' : 'production'} raw image keeps author styles and has dimensions before download`, () => {
    const style = 'width: auto; max-width: min(100%, 630px); height: auto;';
    const tree = { type: 'root', children: [{ type: 'element', tagName: 'img', properties: { src: 'image-1.png', style }, children: [] }] };
    const output = createMediaPlugins({ dev }).rehypeMedia()(tree, vfile);
    const image = output.children[0].properties;
    assert.equal(image.width, dimensions.width);
    assert.equal(image.height, dimensions.height);
    assert.equal(image.style, style);
    assert.equal(image.loading, 'lazy');
    assert.notEqual(image.src, 'image-1.png');
  });
  test(`${dev ? 'development' : 'production'} Markdown images carry dimensions into generated HTML`, () => {
    const image = { type: 'image', url: 'image-1.png', alt: 'photo' };
    const tree = { type: 'root', children: [{ type: 'paragraph', children: [image] }] };
    createMediaPlugins({ dev }).remarkMedia()(tree, vfile);
    assert.equal(image.data.hProperties.width, dimensions.width);
    assert.equal(image.data.hProperties.height, dimensions.height);
    assert.equal(image.data.hProperties.loading, 'lazy');
    assert.notEqual(image.url, 'image-1.png');
  });
}
