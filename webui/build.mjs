import { build } from 'esbuild';
import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const staticRoot = resolve(root, '../src/xrtm/product/webui_static');
const vendorRoot = resolve(staticRoot, 'vendor');
mkdirSync(vendorRoot, { recursive: true });

await build({
  entryPoints: [resolve(root, 'src/index.tsx')],
  bundle: true,
  format: 'iife',
  platform: 'browser',
  target: ['es2020'],
  outfile: resolve(staticRoot, 'app.js'),
  jsxFactory: 'React.createElement',
  jsxFragment: 'React.Fragment',
  banner: {
    js: '/* eslint-disable */',
  },
});

copyFileSync(resolve(root, 'src/styles.css'), resolve(staticRoot, 'app.css'));
copyFileSync(resolve(root, 'node_modules/react/umd/react.production.min.js'), resolve(vendorRoot, 'react.production.min.js'));
copyFileSync(resolve(root, 'node_modules/react-dom/umd/react-dom.production.min.js'), resolve(vendorRoot, 'react-dom.production.min.js'));
