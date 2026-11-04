import test from 'node:test';
import assert from 'node:assert/strict';
import {createMediaPlugins, reserveMediaSpace, POSTS_DIR, readManifest} from './media.mjs';

const slug='plog_202607-202610';
const meta=readManifest()[`${slug}/image.png`];
test('raw HTML auto dimensions reserve a box while retaining the authored display cap',()=>{
  const {rehypeMedia}=createMediaPlugins({dev:false});
  const tree=rehypeMedia()({type:'root',children:[{type:'raw',value:'<img src="image.png" style="width:auto;max-width:min(100%,640px);height:auto">'}]},{path:`${POSTS_DIR}/${slug}/index.md`});
  const p=tree.children[0].properties;
  assert.equal(p.width,meta.width);assert.equal(p.height,meta.height);
  assert.match(p.style,/max-width:min\(100%,640px\)/);
  assert.match(p.style,/width:min\(1086px, 100%,/);
  assert.match(p.style,/aspect-ratio:1086 \/ 946/);
  assert.equal(p.loading,'lazy');
});
test('Markdown URL rewriting carries dimensions into the rendered image',()=>{
  const {remarkMedia}=createMediaPlugins({dev:false});
  const img={type:'image',url:'image.png',alt:'image'};
  remarkMedia()({type:'root',children:[img]},{path:`${POSTS_DIR}/${slug}/index.md`});
  assert.match(img.url,/^https:\/\/img.polebug.com\//);
  assert.equal(img.data.hProperties.width,meta.width);
  assert.equal(img.data.hProperties.height,meta.height);
  assert.ok(img.data.hProperties.style.includes('aspect-ratio:'));
});
test('local previews retain known dimensions and explicit author widths',()=>{
  const {remarkMedia}=createMediaPlugins({dev:true});
  const img={type:'image',url:'image.png',alt:'image'};
  remarkMedia()({type:'root',children:[img]},{path:`${POSTS_DIR}/${slug}/index.md`});
  assert.equal(img.data.hProperties.width,meta.width);
  const p={width:300,style:'width:50%;max-width:600px'};reserveMediaSpace(p,800,600);
  assert.equal(p.height,225);assert.match(p.style,/width:min\(50%,/);assert.match(p.style,/max-width:600px/);
});
