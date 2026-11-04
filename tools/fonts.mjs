// Upload immutable public font assets before switching the site to their new URLs.
// Re-run after upgrading @fontsource; CI needs no storage credentials.
import fs from 'node:fs';
import path from 'node:path';
import { getFontBundle, FONT_MANIFEST, FONT_CACHE_CONTROL, FONT_CACHE_DIR, SUBSET_MANIFEST, readSubsetManifest } from '../blog/lib/fonts.mjs';
const subsetManifest = readSubsetManifest({pending:true}) || readSubsetManifest();
const subsets = subsetManifest ? [subsetManifest.shared, ...Object.values(subsetManifest.pages).map(p=>p.font)].filter(Boolean) : [];
const assets = [...new Map([...getFontBundle().assets, ...subsets.map(a=>({...a,filename:path.join(FONT_CACHE_DIR,path.basename(a.key))}))].map(a=>[a.key,a])).values()];
if (!process.argv.includes('--upload')) {
  console.log(`${assets.length} font files, ${(assets.reduce((n,a)=>n+a.bytes,0)/1024/1024).toFixed(2)} MiB`);
  process.exit(0);
}
process.loadEnvFile(new URL('../.env', import.meta.url));
for (const key of ['R2_ACCOUNT_ID','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','R2_BUCKET']) {
  if (!process.env[key]) throw new Error(`Missing ${key}`);
}
const { S3Client, HeadObjectCommand, PutObjectCommand } = await import('@aws-sdk/client-s3');
const client = new S3Client({region:'auto',endpoint:`https://${process.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,credentials:{accessKeyId:process.env.R2_ACCESS_KEY_ID,secretAccessKey:process.env.R2_SECRET_ACCESS_KEY},maxAttempts:4});
const queue = [...assets];
let uploaded = 0;
await Promise.all(Array.from({length:6}, async () => {
  while(queue.length) {
    const asset = queue.shift();
    const location = {Bucket:process.env.R2_BUCKET,Key:asset.key};
    let existing;
    try { existing = await client.send(new HeadObjectCommand(location)); }
    catch (e) { if(e.$metadata?.httpStatusCode !== 404) throw e; }
    if (existing?.ContentLength !== asset.bytes || existing?.CacheControl !== FONT_CACHE_CONTROL || existing?.ContentType !== 'font/woff2') {
      if (!fs.existsSync(asset.filename)) throw new Error(`Missing generated font ${asset.key}. Run npm run fonts:prepare first.`);
      await client.send(new PutObjectCommand({...location,Body:fs.readFileSync(asset.filename),ContentType:'font/woff2',CacheControl:FONT_CACHE_CONTROL}));
      uploaded++;
    }
  }
}));
fs.writeFileSync(FONT_MANIFEST, JSON.stringify({keys:assets.map(a=>a.key)},null,2)+'\n');
if (subsetManifest) fs.writeFileSync(SUBSET_MANIFEST,JSON.stringify(subsetManifest,null,2)+'\n');
console.log(`Verified ${assets.length} public fonts; uploaded ${uploaded}. Cache: ${FONT_CACHE_CONTROL}`);
