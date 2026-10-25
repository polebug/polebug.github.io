// Split house.glb and plants.glb into the build's download batches (2026-10-22): the yard first, then
// floor 1 (with the whole shell and roof, which rise floor by floor), floor 2, floor 3. The page starts the
// yard as soon as its batch is in and fetches the rest while the yard and the lower floors are built.
//
//   cd web/tools/node && node split_house.mjs
//
// Reads web/house/assets/house.glb and plants.glb (as export_web.py + meshopt left them), writes
// house_<batch>.glb, plants_<batch>.glb and batches.json (the files of each batch, and the heights the
// page's timeline needs before the floors arrive: each floor's furniture range, each slab's underside).
// Run again after every export.
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { prune } from '@gltf-transform/functions';
import { MeshoptDecoder, MeshoptEncoder } from 'meshoptimizer';
import fs from 'node:fs';

import { fileURLToPath } from 'node:url';
const A = fileURLToPath(new URL('../../house/assets/', import.meta.url));
await MeshoptDecoder.ready; await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ 'meshopt.decoder': MeshoptDecoder, 'meshopt.encoder': MeshoptEncoder });
const BATCHES = ['yard', 'floor1', 'floor2', 'floor3'];

// world-space positions of a node's mesh
function worldPositions(node) {
  const out = [], m = node.getWorldMatrix(), mesh = node.getMesh();
  if (!mesh) return out;
  const v = [0, 0, 0];
  for (const p of mesh.listPrimitives()) {
    const a = p.getAttribute('POSITION');
    for (let i = 0; i < a.getCount(); i++) {
      a.getElement(i, v);
      out.push([m[0] * v[0] + m[4] * v[1] + m[8] * v[2] + m[12], m[1] * v[0] + m[5] * v[1] + m[9] * v[2] + m[13],
                m[2] * v[0] + m[6] * v[1] + m[10] * v[2] + m[14]]);
    }
  }
  return out;
}
const yRange = ps => ps.reduce(([lo, hi], p) => [Math.min(lo, p[1]), Math.max(hi, p[1])], [Infinity, -Infinity]);

// ---- which batch a top node goes to
const base = n => n.replace(/\.\d{3}$/, '');
let FLOORS = [];
function houseBatch(name) {
  const n = base(name);
  if (/^(BAKED_yard|BAKED_land|Lake|Cam_)/.test(n)) return 'yard';
  if (/^(BAKED_house|BAKED_floors|BAKED_rugs|BAKED_floor1|Window glass|F1 )/.test(n)) return 'floor1';
  if (/^(BAKED_boards|BAKED_floor2|F2 )/.test(n)) return 'floor2';
  if (/^(BAKED_floor3|F3 )/.test(n)) return 'floor3';
  throw new Error('no batch for house node ' + name);
}
function plantBatch(node) {
  const n = node.getName();
  if (/^(BRANCH_G|LIT_G |FERN_G|LIT_Lake|TWIG_)/.test(n)) return 'yard';
  const f = /^LIT_F(\d) /.exec(n);
  if (f) return 'floor' + f[1];
  if (/^LIT_PH /.test(n)) {                         // pot plants: by the floor they stand on
    let ps = [];
    node.traverse(c => { ps = ps.concat(worldPositions(c)); });
    const y = yRange(ps)[0];
    return y < FLOORS[1][0] - 0.2 ? 'floor1' : y < FLOORS[2][0] - 0.2 ? 'floor2' : 'floor3';
  }
  throw new Error('no batch for plant node ' + n);
}

// ---- heights for the page's plan (the same sums the page did on the whole house)
{
  const doc = await io.read(A + 'house.glb');
  const nodes = doc.getRoot().listNodes();
  for (let f = 1; f <= 3; f++) FLOORS[f - 1] = yRange(worldPositions(nodes.find(n => base(n.getName()) === `BAKED_floor${f}`)));
  const slabPs = worldPositions(nodes.find(n => base(n.getName()) === 'BAKED_floors'));
  var SLAB = [1, 2].map(f => {                      // the slab under floor f + 1: its lowest point within 0.6 m
    const top = FLOORS[f][0];
    let lo = top;
    for (const p of slabPs) if (p[1] > top - 0.6 && p[1] < lo) lo = p[1];
    return lo - 0.02;
  });
}

// ---- write the batches
const files = Object.fromEntries(BATCHES.map(b => [b, []]));
for (const [src, pick] of [['house', n => houseBatch(n.getName())], ['plants', plantBatch]]) {
  for (const b of BATCHES) {
    const doc = await io.read(A + src + '.glb');
    const scene = doc.getRoot().listScenes()[0];
    let kept = 0;
    for (const n of scene.listChildren()) {
      if (pick(n) === b) { kept++; continue; }
      n.traverse(c => c.dispose());
    }
    if (!kept) continue;
    await doc.transform(prune());
    const out = `${src}_${b}.glb`;
    await io.write(A + out, doc);
    files[b].push(out);
    console.log(out, kept, 'nodes', (fs.statSync(A + out).size / 1048576).toFixed(2), 'MB');
  }
}
// the other files each batch brings
files.yard.push('plants.json');
files.floor1.push('linen.webp', 'empty_house.webp', 'empty_floors.webp', 'empty_rugs.webp');
files.floor2.push('empty_boards.webp');
const size = f => fs.statSync(A + f).size;
const out = { floors: FLOORS, slab: SLAB,
  batches: BATCHES.map(b => ({ name: b, files: files[b].map(f => ({ file: f, bytes: size(f) })) })) };
fs.writeFileSync(A + 'batches.json', JSON.stringify(out, null, 1));
for (const b of out.batches) console.log(b.name, (b.files.reduce((a, f) => a + f.bytes, 0) / 1048576).toFixed(2), 'MB');
console.log('floors', JSON.stringify(FLOORS), 'slab', JSON.stringify(SLAB));
