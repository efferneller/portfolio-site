"""Publish the static build over explicit FTPS, with certificate validation."""
import ftplib
import io
import json
import os
from pathlib import Path
import re
import ssl


class HostingFTP(ftplib.FTP_TLS):
    def ntransfercmd(self, cmd, rest=None):
        connection, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            connection = self.context.wrap_socket(
                connection, server_hostname=self.host, session=self.sock.session
            )
        return connection, size


def build_files(directory):
    for page in ['index.html', 'case01/index.html', 'case02/index.html', 'case03/index.html']:
        if not (directory / page).is_file() or not (directory / page).stat().st_size:
            raise ValueError(f'Build is missing {page}')
    manifest = json.loads((directory / 'static/optimized/manifest.json').read_text())
    originals = {source.lstrip('/') for source in manifest}
    files = [file for file in directory.rglob('*') if file.is_file()
             and file.relative_to(directory).as_posix() not in originals | {'.htaccess'}]
    return sorted(files, key=lambda file: (file.suffix == '.html', file.as_posix()))


def ensure_directory(ftp, root, relative):
    ftp.cwd(root)
    for part in relative.parts:
        try:
            ftp.cwd(part)
        except ftplib.error_perm:
            ftp.mkd(part)
            ftp.cwd(part)


def merge_cache(existing, configuration):
    begin, end = b'# BEGIN portfolio cache', b'# END portfolio cache'
    if configuration.count(begin) != 1 or configuration.count(end) != 1:
        raise ValueError('Invalid local cache configuration')
    block = configuration[configuration.index(begin):configuration.index(end) + len(end)]
    if not existing.count(begin) and not existing.count(end):
        return existing + (b'\n' if existing and not existing.endswith(b'\n') else b'') + block + b'\n'
    if existing.count(begin) != 1 or existing.count(end) != 1 or existing.index(begin) > existing.index(end):
        raise ValueError('Invalid remote cache markers; preserve hosting configuration')
    return existing[:existing.index(begin)] + block + existing[existing.index(end) + len(end):]


def configure_cache(ftp, directory, root):
    ftp.cwd(root)
    previous = io.BytesIO()
    try:
        ftp.retrbinary('RETR .htaccess', previous.write)
    except ftplib.error_perm as error:
        if not str(error).startswith('550'):
            raise
        # 550 can also mean unreadable: confirm absence instead of overwriting.
        if '.htaccess' in [name.rsplit('/', 1)[-1] for name in ftp.nlst()]:
            raise ValueError('Existing .htaccess is unreadable; refusing to replace it') from error
    existing = previous.getvalue()
    updated = merge_cache(existing, (directory / '.htaccess').read_bytes())
    if updated != existing:
        ftp.storbinary('STOR .htaccess.deploying', io.BytesIO(updated))
        ftp.rename('.htaccess.deploying', '.htaccess')
        print('Updated managed cache block; preserved hosting rules.')


def deploy(ftp, directory, root):
    files = build_files(directory)
    # A typo in the root must stop before creating directories or uploading.
    ftp.cwd(root)
    ftp.voidcmd('TYPE I')
    if not ftp.size('index.html'):
        raise ValueError('Destination must contain the existing site index.html')
    uploaded = skipped = 0
    cache_configured = False
    for file in files:
        if file.suffix == '.html' and not cache_configured:
            configure_cache(ftp, directory, root)
            cache_configured = True
        relative = file.relative_to(directory)
        ensure_directory(ftp, root, relative.parent)
        # A content hash identifies immutable optimized images. Other files are
        # always replaced, including same-size changes to HTML, CSS and JS.
        hashed = relative.as_posix().startswith('static/optimized/') and re.search(
            r'\.[0-9a-f]{12}\.(webp|png)$', file.name
        )
        if hashed:
            try:
                if ftp.size(file.name) == file.stat().st_size:
                    skipped += 1
                    continue
            except ftplib.error_perm as error:
                if not str(error).startswith('550'):
                    raise
        temporary = f'.{file.name}.deploying'
        with file.open('rb') as stream:
            ftp.storbinary(f'STOR {temporary}', stream)
        ftp.rename(temporary, file.name)
        uploaded += 1
        print(f'Uploaded {relative.as_posix()}')
    print(f'Published: {uploaded} files; reused {skipped} hashed images.')


def main():
    password = os.environ.get('REG_FTP_PASSWORD')
    if not password:
        raise SystemExit('Add the REG_FTP_PASSWORD repository secret in GitHub Actions.')
    host = os.environ.get('REG_FTP_HOST', 'server26.hosting.reg.ru')
    user = os.environ.get('REG_FTP_USER', 'u3700684')
    root = os.environ.get('REG_FTP_ROOT', '/www/efferneller.ru')
    if root.rstrip('/') != '/www/efferneller.ru':
        raise SystemExit('Unexpected deployment folder; verify it before changing the script.')
    directory = Path(__file__).resolve().parent.parent / 'dist'
    build_files(directory)
    with HostingFTP(context=ssl.create_default_context(), timeout=60) as ftp:
        ftp.connect(host, 21)
        ftp.auth()  # Verify the server before sending login or password.
        ftp.login(user, password)
        ftp.prot_p()
        deploy(ftp, directory, root)


if __name__ == '__main__':
    main()
