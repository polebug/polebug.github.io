// Put re-baked lightmaps into house.glb without re-exporting it (2026-10-23): each bake_<g>.png named on
// the command line replaces the house.glb image of the same name, as WebP q88 (as export_web.py writes
// them). Geometry, UVs and everything else stay as they are. Pair with export_web.py WEB_ON_PROXIES=1.
//   cd web/tools/node && node swap_bakes.mjs house yard
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS, EXTMeshoptCompression } from '@gltf-transform/extensions';
import { MeshoptDecoder, MeshoptEncoder } from 'meshoptimizer';
import sharp from 'sharp';
import { fileURLToPath } from 'node:url';
await Promise.all([MeshoptDecoder.ready, MeshoptEncoder.ready]);
const P = fileURLToPath(new URL('../../../', import.meta.url));
const GLB = P + 'web/house/assets/house.glb';
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ 'meshopt.decoder': MeshoptDecoder, 'meshopt.encoder': MeshoptEncoder });
const doc = await io.read(GLB);
for (const g of process.argv.slice(2)) {
  const tex = doc.getRoot().listTextures().find(t => t.getName() === 'bake_' + g);
  if (!tex) throw new Error('no image bake_' + g + ' in house.glb');
  const webp = await sharp(P + `assets/web-build/bake_${g}.png`).webp({ quality: 88 }).toBuffer();
  console.log('bake_' + g, Math.round(tex.getImage().byteLength / 1024), '->', Math.round(webp.byteLength / 1024), 'KB');
  tex.setImage(new Uint8Array(webp)).setMimeType('image/webp');
}
doc.createExtension(EXTMeshoptCompression).setRequired(true)
  .setEncoderOptions({ method: EXTMeshoptCompression.EncoderMethod.QUANTIZE });
await io.write(GLB, doc);
