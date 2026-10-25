import { defineConfig } from 'astro/config';
import { createMediaPlugins } from './lib/media.mjs';

const dev = process.argv.includes('dev');
const { remarkMedia, rehypeMedia, integration } = createMediaPlugins({ dev });

export default defineConfig({
  site: 'https://blog.polebug.com',
  trailingSlash: 'ignore',
  build: { format: 'directory' },
  markdown: {
    remarkPlugins: [remarkMedia],
    rehypePlugins: [rehypeMedia],
    shikiConfig: { theme: 'vitesse-dark' },
  },
  integrations: [integration],
  devToolbar: { enabled: false },
});
