import { createHash } from 'node:crypto';
import { cp, mkdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const output = resolve(root, 'dist');
const entries = ['index.html', 'case01', 'case02', 'case03', 'src', 'static', '.htaccess'];
const pages = ['index.html', 'case01/index.html', 'case02/index.html', 'case03/index.html'];
const manifestFile = 'static/optimized/manifest.json';

async function imageManifest(directory = root) {
  return JSON.parse(await readFile(resolve(directory, manifestFile), 'utf8'));
}

function optimizedHtml(html, manifest) {
  return html.replace(/\bsrc="(\/static\/[^"\s]+\.png)"/g, (_, source) => {
    if (source.startsWith('/static/optimized/')) return `src="${source}"`;
    const image = manifest[source];
    if (!image) throw new Error(`Missing optimized image: ${source}. Run npm run images:optimize.`);
    return `src="${image.src}"`;
  });
}

async function applicationAssets() {
  const files = new Map();
  const urls = new Map();
  function add(name, content) {
    const extension = extname(name);
    const hash = createHash('sha256').update(content).digest('hex').slice(0, 12);
    const filename = `${name.slice(0, -extension.length)}.${hash}${extension}`;
    files.set(`src/${filename}`, content);
    urls.set(`/src/${name}`, `/src/${filename}`);
    return filename;
  }
  add('styles.css', await readFile(resolve(root, 'src/styles.css')));
  const loader = add('page-loader.js', await readFile(resolve(root, 'src/page-loader.js')));
  const main = (await readFile(resolve(root, 'src/main.js'), 'utf8'))
    .replaceAll('./page-loader.js', `./${loader}`);
  add('main.js', main);
  return { files, urls };
}

async function verifyImages(manifest) {
  for (const [source, image] of Object.entries(manifest)) {
    for (const [url, expectedHash] of [[source, image.sourceSha256], [image.src, image.outputSha256]]) {
      const data = await readFile(resolve(root, `.${url}`));
      const hash = createHash('sha256').update(data).digest('hex');
      if (hash !== expectedHash) throw new Error(`Image changed: ${url}. Run npm run images:optimize.`);
    }
  }
}

async function build() {
  // Validate source files before replacing an existing successful build.
  await Promise.all(entries.map((entry) => stat(resolve(root, entry))));
  const manifest = await imageManifest();
  await verifyImages(manifest);
  const assets = await applicationAssets();
  const htmlPages = await Promise.all(pages.map(async (page) => [
    page, [...assets.urls].reduce(
      (html, [before, after]) => html.replaceAll(`"${before}"`, `"${after}"`),
      optimizedHtml(await readFile(resolve(root, page), 'utf8'), manifest),
    ),
  ]));
  await rm(output, { recursive: true, force: true });
  await mkdir(output, { recursive: true });
  await Promise.all(entries.map((entry) => cp(resolve(root, entry), resolve(output, entry), {
    recursive: true,
    filter: (path) => !path.endsWith('.DS_Store'),
  })));
  await Promise.all([...assets.files].map(([file, content]) => writeFile(resolve(output, file), content)));
  await Promise.all(htmlPages.map(([page, html]) => writeFile(resolve(output, page), html)));
  console.log('Static site built in dist/');
}

const mimeTypes = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.avif': 'image/avif',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.otf': 'font/otf',
  '.ttf': 'font/ttf',
};

function serve(directory) {
  const port = Number(process.env.PORT || 5173);
  createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      let path = resolve(directory, `.${pathname}`);
      if (path !== directory && !path.startsWith(`${directory}${sep}`)) {
        response.writeHead(403).end('Forbidden');
        return;
      }
      if ((await stat(path)).isDirectory()) path = resolve(path, 'index.html');
      let body = await readFile(path);
      if (extname(path) === '.html') {
        body = Buffer.from(optimizedHtml(body.toString('utf8'), await imageManifest(directory)));
      }
      response.writeHead(200, {
        'Content-Type': mimeTypes[extname(path)] || 'application/octet-stream',
        'Cache-Control': 'no-store',
      });
      response.end(request.method === 'HEAD' ? undefined : body);
    } catch {
      response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Страница не найдена');
    }
  }).listen(port, '127.0.0.1', () => {
    console.log(`Local: http://127.0.0.1:${port}`);
  });
}

if (process.argv.includes('--serve')) {
  serve(root.replace(/\/$/, ''));
} else if (process.argv.includes('--preview')) {
  await stat(resolve(output, 'index.html'));
  serve(output);
} else {
  await build();
}
