import { cp, mkdir, readFile, rm, stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const output = resolve(root, 'dist');
const entries = ['index.html', 'case01', 'case02', 'case03', 'src', 'static'];

async function build() {
  // Validate source files before replacing an existing successful build.
  await Promise.all(entries.map((entry) => stat(resolve(root, entry))));
  await rm(output, { recursive: true, force: true });
  await mkdir(output, { recursive: true });
  await Promise.all(entries.map((entry) => cp(resolve(root, entry), resolve(output, entry), {
    recursive: true,
    filter: (path) => !path.endsWith('.DS_Store'),
  })));
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
      const body = await readFile(path);
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
