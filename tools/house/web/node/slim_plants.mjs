// Slim plants.glb for the web (2026-10-22): run after each export_web.py export.
//   node slim_plants.mjs ../../house/assets/plants.glb ../../house/assets/plants.glb
// 1. Drops what the page never reads: every plant is drawn with a MeshBasicMaterial (house/index.html,
//    setupPlants), so normals, normal/roughness/occlusion maps and material extensions go.
// 2. Halves the three potted_plant_01 pots (107k triangles each; 1-2 % of pixels change close up)
//    and the 2K bark and rock colour maps (no visible change at the page's distances).
// 3. Removes the six Searsia shrubs (user, 10-23: 「把灌木移除」); their slots stay in pieces.json, empty,
//    so the yard keeps its order and pace.
// 23.7 MB -> 14.2 MB (-> about 10 MB without the shrubs).
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS, EXTMeshoptCompression } from '@gltf-transform/extensions';
import { prune, reorder, simplifyPrimitive, textureCompress } from '@gltf-transform/functions';
import { MeshoptDecoder, MeshoptEncoder, MeshoptSimplifier } from 'meshoptimizer';
import sharp from 'sharp';
await Promise.all([MeshoptDecoder.ready, MeshoptEncoder.ready, MeshoptSimplifier.ready]);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ 'meshopt.decoder': MeshoptDecoder, 'meshopt.encoder': MeshoptEncoder });
const [src, out] = process.argv.slice(2);
const doc = await io.read(src);
const root = doc.getRoot();

for (const n of root.listNodes()) if (/^LIT_G shrub /.test(n.getName())) n.dispose();
for (const m of root.listMeshes()) for (const p of m.listPrimitives()) if (p.getAttribute('NORMAL')) p.setAttribute('NORMAL', null);
for (const m of root.listMaterials()) {
  m.setNormalTexture(null); m.setMetallicRoughnessTexture(null); m.setOcclusionTexture(null); m.setEmissiveTexture(null);
  for (const e of m.listExtensions()) m.setExtension(e.extensionName, null);
}
for (const m of root.listMeshes()) for (const p of m.listPrimitives())
  if (p.getMaterial()?.getName().startsWith('potted_plant_01'))
    simplifyPrimitive(p, { simplifier: MeshoptSimplifier, ratio: 0.5, error: 0.01, lockBorder: true });

await doc.transform(
  textureCompress({ encoder: sharp, targetFormat: 'webp', resize: [1024, 1024], quality: 88, pattern: /^(Bark014|Rock063)/ }),
  reorder({ encoder: MeshoptEncoder, target: 'size' }),
  prune({ keepAttributes: true, keepLeaves: true }));
doc.createExtension(EXTMeshoptCompression).setRequired(true)
  .setEncoderOptions({ method: EXTMeshoptCompression.EncoderMethod.QUANTIZE });
await io.write(out, doc);
