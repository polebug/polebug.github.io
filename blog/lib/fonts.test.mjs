import test from 'node:test';
import assert from 'node:assert/strict';
import {getFontBundle, getPageFontStyles, readSubsetManifest} from './fonts.mjs';

function faces(css) {
  return [...css.matchAll(/@font-face\s*\{([^}]+)\}/g)].map(([,body])=>{
    const range=body.match(/unicode-range:\s*([^;}]+)/)?.[1];
    const points=new Set();
    for(const part of (range||'').split(',').filter(Boolean)){
      const [a,b=a]=part.trim().replace(/^U\+/i,'').split('-').map(n=>parseInt(n,16));
      for(let cp=a;cp<=b;cp++) points.add(cp);
    }
    return {points, subset:/noto-(common|page)\./.test(body)};
  });
}
const manifest=readSubsetManifest({pending:true}) || readSubsetManifest();
const original=new Set(faces(getFontBundle().chineseCss).flatMap(f=>[...f.points]));
const actualGlyphs=()=>manifest.fallbackRanges ? new Set(faces(Object.values(manifest.fallbackRanges).map(range=>`@font-face{unicode-range:${range};}`).join('')).flatMap(f=>[...f.points])) : original;

test('page subsets preserve fallback coverage for future edits without duplicate glyph downloads',()=>{
  assert.ok(manifest);
  for(const route of Object.keys(manifest.pages)){
    const all=faces(getPageFontStyles(route,{published:manifest}));
    const covered=new Set(all.filter(f=>f.subset).flatMap(f=>[...f.points]));
    const fallback=new Set(all.filter(f=>!f.subset).flatMap(f=>[...f.points]));
    assert.deepEqual(new Set([...covered,...fallback]),actualGlyphs(),`Lost original font coverage on ${route}`);
    assert.equal([...covered].some(cp=>fallback.has(cp)),false,`Duplicate font ranges on ${route}`);
  }
});
test('new routes and unavailable manifests retain the original glyph coverage',()=>{
  for(const published of [manifest,null]){
    const css=getPageFontStyles('/new-article/',{published});
    assert.deepEqual(new Set(faces(css).flatMap(f=>[...f.points])),published ? actualGlyphs() : original);
  }
});
test('trailing slash variants select the same article supplement',()=>{
  const route=Object.keys(manifest.pages).find(p=>/^\/\d{4}\//.test(p));
  assert.equal(getPageFontStyles(route,{published:manifest}),getPageFontStyles(route.slice(0,-1),{published:manifest}));
});
