import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { MeshoptDecoder } from 'meshoptimizer';
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.decoder': MeshoptDecoder });
const doc = await io.read(process.argv[2]);
for (const n of doc.getRoot().listNodes()) {
  if (!/shrub_0|shrub 0|PH Money/.test(n.getName())) continue;
  const m = n.getMesh(); if (!m) continue;
  console.log('NODE', n.getName(), 'prims', m.listPrimitives().length);
  for (const p of m.listPrimitives()) { const mat = p.getMaterial(); console.log('  mat', mat && mat.getName(), 'baseTex', !!(mat && mat.getBaseColorTexture()), 'alphaMode', mat && mat.getAlphaMode(), 'attrs', p.listSemantics().join(',')); }
}
