import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, cp, rm, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

test('build versions styles and the complete module import chain', async () => {
  const root = await mkdtemp(join(tmpdir(), 'portfolio-assets-'));
  try {
    await cp(new URL('../build.mjs', import.meta.url), join(root, 'build.mjs'));
    for (const directory of ['src', 'static/optimized', 'case01', 'case02', 'case03']) {
      await mkdir(join(root, directory), { recursive: true });
    }
    const pages = ['index.html', 'case01/index.html', 'case02/index.html', 'case03/index.html'];
    for (const page of pages) await writeFile(join(root, page), '<link href="/src/styles.css"><link href="/src/page-loader.js"><script src="/src/main.js"></script>');
    await writeFile(join(root, 'static/optimized/manifest.json'), '{}');
    await writeFile(join(root, '.htaccess'), '# cache');
    await writeFile(join(root, 'src/styles.css'), 'body { color: black }');
    await writeFile(join(root, 'src/page-loader.js'), 'export const version = 1;');
    await writeFile(join(root, 'src/main.js'), 'import { version } from "./page-loader.js";');
    const build = async () => {
      execFileSync(process.execPath, [join(root, 'build.mjs')]);
      return (await readdir(join(root, 'dist/src'))).filter(name => /\.[a-f0-9]{12}\./.test(name)).sort();
    };
    const first = await build();
    assert.equal(first.length, 3);
    assert.deepEqual(await build(), first);
    await writeFile(join(root, 'src/page-loader.js'), 'export const version = 2;');
    const next = await build();
    assert.equal(first.find(name => name.startsWith('styles.')), next.find(name => name.startsWith('styles.')));
    assert.notEqual(first.find(name => name.startsWith('main.')), next.find(name => name.startsWith('main.')));
    for (const page of pages) {
      const html = await readFile(join(root, 'dist', page), 'utf8');
      for (const name of next) assert.ok(html.includes(`/src/${name}`));
    }
    const main = await readFile(join(root, 'dist/src', next.find(name => name.startsWith('main.'))), 'utf8');
    assert.ok(main.includes(`./${next.find(name => name.startsWith('page-loader.'))}`));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
