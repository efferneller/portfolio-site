let pageReady;

function loadImage(image, retry) {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      image.removeEventListener('load', loaded);
      image.removeEventListener('error', failed);
    };
    const failed = () => {
      cleanup();
      reject(new Error('Image failed to load'));
    };
    const loaded = async () => {
      cleanup();
      try {
        if (!image.naturalWidth) throw new Error('Image has no pixels');
        if (typeof image.decode === 'function') await image.decode();
        resolve();
      } catch (error) {
        reject(error);
      }
    };

    image.addEventListener('load', loaded, { once: true });
    image.addEventListener('error', failed, { once: true });
    image.loading = 'eager';
    if (retry) {
      const url = new URL(image.currentSrc || image.src, document.baseURI);
      url.searchParams.set('page-loader-retry', `${Date.now()}-${Math.random().toString(36).slice(2)}`);
      image.src = url.href;
    }
    if (image.complete) {
      if (image.naturalWidth) loaded();
      else failed();
    }
  });
}

export function startPageLoader() {
  if (pageReady) return pageReady;
  const loader = document.querySelector('[data-page-loader]');
  const main = document.querySelector('main');
  if (!loader || !main) {
    document.documentElement.classList.remove('is-loading');
    return Promise.resolve();
  }

  const status = loader.querySelector('[data-loader-status]');
  const percent = loader.querySelector('[data-loader-percent]');
  const progress = loader.querySelector('[data-loader-progress]');
  const retryButton = loader.querySelector('[data-loader-retry]');
  const images = [...main.querySelectorAll('img')];
  const completed = new Set();
  let running = false;
  let finish;
  pageReady = new Promise((resolve) => { finish = resolve; });

  document.documentElement.classList.add('is-loading');
  main.setAttribute('aria-busy', 'true');
  main.setAttribute('inert', '');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');

  const updateProgress = () => {
    const fraction = images.length ? completed.size / images.length : 1;
    const value = Math.floor(fraction * 100);
    progress.style.setProperty('--progress', fraction);
    progress.setAttribute('aria-valuenow', value);
    percent.textContent = `${value}%`;
  };

  async function run(retry = false) {
    if (running) return;
    running = true;
    retryButton.hidden = true;
    status.textContent = 'Загружаем изображения';
    updateProgress();
    let fontsReady = false;
    let failed = false;
    const fonts = Promise.resolve(document.fonts?.ready).then(() => {
      fontsReady = true;
    }).catch(() => { failed = true; });

    await Promise.all([
      fonts,
      ...images.filter((image) => !completed.has(image)).map(async (image) => {
        try {
          await loadImage(image, retry);
          completed.add(image);
          updateProgress();
          if (completed.size === images.length && !fontsReady) {
            status.textContent = 'Подготавливаем страницу';
          }
        } catch {
          failed = true;
        }
      }),
    ]);
    running = false;

    if (failed) {
      status.textContent = 'Не удалось завершить загрузку. Попробуйте ещё раз.';
      retryButton.hidden = false;
      return;
    }

    main.removeAttribute('aria-busy');
    main.removeAttribute('inert');
    loader.hidden = true;
    document.documentElement.classList.remove('is-loading');
    finish();
  }

  retryButton.addEventListener('click', () => { run(true); });
  run();
  return pageReady;
}
