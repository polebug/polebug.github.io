# polebug.com

My corner of the internet: a homepage with a little 3D companion house, and a blog.

| | Address | Source | Hosted on |
|---|---|---|---|
| Homepage + house | [polebug.com](https://polebug.com) | `home/` (static files) | Cloudflare Pages |
| Blog | [blog.polebug.com](https://blog.polebug.com) | `blog/` (Astro) | GitHub Pages, built by GitHub Actions on push |
| Post images & videos | img.polebug.com | not in git | Cloudflare R2 |

```
blog/
  posts/<slug>/index.md   published posts (the URL is /yyyy/mm/dd/<slug>/ from the post's date)
  posts/<slug>/*.jpg …    their images and videos — kept on this computer, uploaded to R2, ignored by git
  drafts/<slug>/          drafts — never committed, shown only in local preview
  media.json              where each uploaded file lives in R2 (committed)
  src/                    layouts, pages, styles
home/                     the homepage and the companion house, served as is
tools/                    dev server, media upload, checks; tools/house/ has the house's Blender/export scripts
```

## Writing a post

```bash
npm install                      # once per computer (Node 22+, and `brew install ffmpeg` for videos)
npm run new my-post "Title"      # creates blog/drafts/my-post/index.md
npm run dev                      # blog http://localhost:4321 (drafts included), home http://localhost:8000
```

Local video previews automatically read dimensions and cache a cover frame. HDR (HLG/PQ)
covers on macOS use AVFoundation's native SDR conversion and the first playback frame
(requires Xcode Command Line Tools). Other platforms use FFmpeg with zscale and tonemap;
set `FFMPEG_PATH` if that binary is not on PATH.
An explicit `poster="cover.jpg"` keeps the cover you choose.

Put images and videos next to `index.md` and reference them by file name, in Markdown or HTML:

```html
![](photo.jpg)
<img src="photo.jpg" width="600">
<video src="clip.MOV" controls></video>            <!-- kept at its own resolution, up to 4K -->
<video src="talk.MOV" quality="1080" controls></video>   <!-- scaled down to 1080p (or 720) -->
```

To publish:

1. Move the folder from `blog/drafts/` to `blog/posts/`.
2. `npm run upload` — compresses images to WebP and videos to H.264 MP4 (+ poster), uploads them to R2,
   backs up the originals in a private bucket, updates `blog/media.json`, and prints R2 usage.
3. `npm run comments:register` — register stable IDs for new articles; commit `blog/comment-documents.json`.
4. `npm run check` — builds the site the way production does and verifies every image, video and link loads.
5. `npm run comments:sync`, then `npx --yes wrangler@4.152.0 d1 execute polebug-comments --remote --config comments/wrangler.toml --file comments/.data/documents.sql` — sync article metadata and text revisions.
6. Commit and push. GitHub Actions builds and deploys in a minute or two.

A post that references a file which was never uploaded fails the build, so nothing goes live half-broken.

Upload needs R2 keys in `.env` (see `.env.example`).
To publish a post's images unchanged, use `npm run upload -- --post <slug> --original-images`.
This preserves the original image files, including their resolution and metadata; later uploads remember this choice for those images. Browser-compatible PNG, JPEG, WebP, GIF and AVIF files are supported.
On a new computer without the original files, the preview falls back to the uploaded copies.

The Archive writing calendar is generated from published posts' `date` fields in Beijing time.
Publishing a new post lights up its date on the next build; drafts and code-only edits do not count.
Use the year selector to browse past years, and click a lit day to jump to its articles.

## Blog fonts

Article cover titles and body copy share the same font family and regular weight.
Content headings use browser-synthesized bold; Latin text uses Lato 400/700.
The Chinese font uses a stable shared set of common characters and runtime UI labels plus a supplement
for each rendered public page. `blog/font-common.txt` keeps the shared set stable
when posts change. The original Fontsource shards remain as a fallback for newly
added characters, new routes, and drafts; a stale subset never hides new text.

`blog/lib/fonts.mjs` generates content-hashed WOFF2 URLs on `img.polebug.com/fonts/`.
Font objects use `public, max-age=31536000, immutable`. Old objects stay available
to cached pages. `blog/fonts.json` records uploaded assets and
`blog/font-subsets.json` records page coverage. Builds validate the upload records;
CI needs neither Python nor R2 credentials and never regenerates fonts.

To refresh subsets after editing posts or upgrading fonts:

```sh
python3 -m venv /tmp/polebug-font-tools
/tmp/polebug-font-tools/bin/pip install -r tools/fonts/requirements.txt
FONT_PYTHON=/tmp/polebug-font-tools/bin/python npm run fonts:prepare
/tmp/polebug-font-tools/bin/python tools/fonts/test_subsets.py
node --test blog/lib/fonts.test.mjs
npm run fonts:upload
npm run build
```

Preparation builds public pages, extracts their rendered text (excluding scripts
and styles), and writes local subsets to ignored `blog/.font-cache/`. It reuses the
installed Fontsource glyphs and checks their horizontal metrics. The tests check
coverage, outlines, metrics, runtime UI glyphs, non-overlapping ranges, and page
font size reductions. Supplement ranges are removed from fallback faces to avoid
duplicate downloads. Some symbols may still require compatibility fallback faces.
Local dev can preview pending subsets without uploading. Upload verifies every
font before updating the published manifests; commit both manifests with the site
changes. New content still works without regeneration, using original fallback
shards for uncovered characters. Use `npm run fonts:prepare -- --refresh-common`
only when intentionally replacing the shared set, since doing so invalidates that cache.

The public media bucket permits anonymous GET/HEAD CORS for fonts (configuration:
`tools/font-cors.json`). This does not grant uploads or private-bucket access.
If the bucket is recreated, apply that file using `wrangler r2 bucket cors set`;
inspect and preserve any existing rules before changing them.

## Comments

Native comments run on Cloudflare Workers + D1 at `comments.polebug.com`. Readers can sign in with GitHub or post as guests; comments publish immediately, and guest verification is remembered for 24 hours in the same browser. The owner manages comments inside the blog comment panel. Existing article comments were imported from GitHub; the original issues remain available.

See [comments/README.md](comments/README.md) for database design, future text annotations, deployment, moderation and backups. Article UUIDs survive URL changes: move the existing registry entry when renaming a slug.

## License

Code: [MIT](LICENSE). Posts, photos, the house's artwork and third-party credits: see [LICENSE-CONTENT.md](LICENSE-CONTENT.md).
