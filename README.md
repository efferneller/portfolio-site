# Портфолио Эллады Ярмоновой

Статический сайт по [макету Figma](https://www.figma.com/design/t7c029bCNiqsBtdT2hwSUf/Portfolio?node-id=214-49941): главная страница и три кейса, адаптированные для desktop и мобильных экранов.

## Локальный запуск

Нужен Node.js 22 или новее. Внешних npm-зависимостей нет.

```sh
npm run dev
```

Сайт доступен по адресу `http://127.0.0.1:5173`. После изменения файлов обновите страницу. Другой порт можно задать через `PORT=5174 npm run dev`.

```sh
npm run build
npm run preview
```

Сборка копирует страницы, стили, скрипты и изображения в `dist/`. Каталог сборки не хранится в Git. Исходные изображения находятся в `static/`.

## Ветки и Netlify

- `dev` — разработка и проверка изменений.
- `main` — публикация сайта.

Репозиторий подключён через Git к [проекту Netlify tiny-blancmange-8aaf3e](https://app.netlify.com/projects/tiny-blancmange-8aaf3e/overview). Production branch — `main`, автоматические сборки включены. Файл `netlify.toml` задаёт команду `npm run build`, каталог публикации `dist` и Node.js 22. Проверка `build.ignore` пропускает автоматические сборки для веток, отличных от `main`.

Production branch хранится в Netlify и не задаётся через `netlify.toml`. Базовый каталог — корень репозитория. Адрес сайта после первой успешной публикации: [tiny-blancmange-8aaf3e.netlify.app](https://tiny-blancmange-8aaf3e.netlify.app/).

До первого переноса сайта из `dev` ветка `main` содержит только README, поэтому её начальная сборка завершилась ошибкой. Для первой публикации нужно перенести реализацию в `main`.

После проверки изменений в `dev` перенесите их в `main`:

```sh
git switch main
git merge dev
git push origin main
```

Push или merge в `main` запускает сборку на стороне Netlify и публикацию содержимого `dist/`. Дополнительный GitHub Actions workflow или токен Netlify не требуется.
