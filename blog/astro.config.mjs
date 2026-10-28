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
    // Both schemes are emitted as CSS variables; prose.css picks one by the <html> theme.
    shikiConfig: { themes: { light: 'vitesse-light', dark: 'vitesse-dark' }, defaultColor: false },
  },
  integrations: [integration],
  devToolbar: { enabled: false },
});
