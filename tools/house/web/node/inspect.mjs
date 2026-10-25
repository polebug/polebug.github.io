import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { MeshoptDecoder } from 'meshoptimizer';
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.decoder': MeshoptDecoder });
for (const f of process.argv.slice(2)) {
  const doc = await io.read(f);
  const root = doc.getRoot();
  const tex = new Map(root.listTextures().map(t => [t, t.getImage()?.byteLength || 0]));
  console.log('==', f, 'scenes', root.listScenes().length, 'top nodes', root.listScenes()[0].listChildren().length);
  const rows = [];
  for (const n of root.listScenes()[0].listChildren()) {
    let bytes = 0, texb = 0; const seen = new Set();
    n.traverse(c => { const m = c.getMesh(); if (!m) return; for (const p of m.listPrimitives()) { for (const a of p.listAttributes()) bytes += a.getArray().byteLength; if (p.getIndices()) bytes += p.getIndices().getArray().byteLength; const mat = p.getMaterial(); if (mat) for (const t of [mat.getBaseColorTexture()]) if (t && !seen.has(t)) { seen.add(t); texb += tex.get(t); } } });
    rows.push([n.getName(), (bytes / 1048576).toFixed(2), (texb / 1048576).toFixed(2), n.getCamera() ? 'cam' : '', n.listChildren().length]);
  }
  rows.sort((a, b) => b[1] - a[1] + (b[2] - a[2]));
  for (const r of rows) console.log(r.join('\t'));
}
