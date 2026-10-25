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
3. `npm run check` — builds the site the way production does and verifies every image, video and link loads.
4. Commit and push. GitHub Actions builds and deploys in a minute or two.

A post that references a file which was never uploaded fails the build, so nothing goes live half-broken.

Upload needs R2 keys in `.env` (see `.env.example`); comments need `blog/.env` (see `blog/.env.example`).
On a new computer without the original files, the preview falls back to the uploaded copies.

## Comments

Gitalk, storing comments as issues in this repository, with the same issue ids as the old Hexo site
(`md5(location.pathname)`), so old comments carry over.

## License

Code: [MIT](LICENSE). Posts, photos, the house's artwork and third-party credits: see [LICENSE-CONTENT.md](LICENSE-CONTENT.md).
