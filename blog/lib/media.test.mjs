import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import fs from 'node:fs';
import { execFileSync, spawnSync } from 'node:child_process';
import { createMediaPlugins, POSTS_DIR, DRAFTS_DIR, CACHE_DIR, readManifest } from './media.mjs';

const slug = 'plog_202607-202610';
const vfile = { path: path.join(POSTS_DIR, slug, 'index.md') };
const dimensions = readManifest()[`${slug}/image-1.png`];

test('a photo with a preceding Markdown caption stays in one pagination block', () => {
  const tree = { type: 'root', children: [{ type: 'element', tagName: 'p', properties: {}, children: [
    { type: 'text', value: '爬升的路线如下：\n' },
    { type: 'element', tagName: 'img', properties: { src: 'image-1.png', alt: '路线' }, children: [] },
  ] }] };
  const figure = createMediaPlugins({ dev: false }).rehypeMedia()(tree, vfile).children[0];
  assert.equal(figure.tagName, 'figure');
  assert(figure.properties.className.includes('media-figure'));
  assert.equal(figure.children[0].tagName, 'figcaption');
  assert.equal(figure.children[0].children[0].value, '爬升的路线如下：\n');
  assert.equal(figure.children[1].tagName, 'img');
  assert.equal(figure.children[1].properties.alt, '路线');
  assert.equal(figure.children[1].properties.width, dimensions.width);
});

test('an image embedded between text stays inline', () => {
  const tree = { type: 'root', children: [{ type: 'element', tagName: 'p', properties: {}, children: [
    { type: 'text', value: 'Before ' },
    { type: 'element', tagName: 'img', properties: { src: 'image-1.png' }, children: [] },
    { type: 'text', value: ' after.' },
  ] }] };
  const paragraph = createMediaPlugins({ dev: false }).rehypeMedia()(tree, vfile).children[0];
  assert.equal(paragraph.tagName, 'p');
  assert.equal(paragraph.children[2].value, ' after.');
});

test('local videos get cached covers, refresh them after replacement, and preserve custom posters', {
  skip: spawnSync('ffmpeg', ['-version']).status !== 0 || spawnSync('ffprobe', ['-version']).status !== 0,
}, () => {
  fs.mkdirSync(DRAFTS_DIR, { recursive: true });
  const dir = fs.mkdtempSync(path.join(DRAFTS_DIR, 'poster-test-'));
  const file = path.join(dir, 'clip.mp4');
  const posters = new Set();
  const makeVideo = color => execFileSync('ffmpeg', [
    '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i', `color=c=${color}:s=160x90:r=10`,
    '-t', '0.2', '-c:v', 'mpeg4', file,
  ]);
  const render = (poster) => {
    const tree = { type: 'root', children: [{ type: 'element', tagName: 'video', properties: {
      src: 'clip.mp4', preload: 'none', ...(poster ? { poster } : {}),
    }, children: [] }] };
    return createMediaPlugins({ dev: true }).rehypeMedia()(tree, { path: path.join(dir, 'index.md') }).children[0].properties;
  };
  try {
    makeVideo('red');
    const first = render();
    posters.add(first.poster);
    assert.match(first.poster, /^\/__local-media\/cache\/\.preview\/.+\.poster\.jpg$/);
    assert.equal(first.preload, 'none');
    assert.equal(first.width, 160);
    assert.equal(first.height, 90);
    const posterFile = path.join(CACHE_DIR, '.preview', path.basename(first.poster));
    assert(fs.statSync(posterFile).size > 0);
    const stamp = fs.statSync(posterFile).mtimeMs;
    assert.equal(render().poster, first.poster);
    assert.equal(fs.statSync(posterFile).mtimeMs, stamp);
    assert.equal(render('https://example.com/custom.jpg').poster, 'https://example.com/custom.jpg');
    makeVideo('blue');
    const second = render();
    posters.add(second.poster);
    assert.notEqual(second.poster, first.poster);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
    for (const poster of posters) if (poster) fs.rmSync(path.join(CACHE_DIR, '.preview', path.basename(poster)), { force: true });
  }
});

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
