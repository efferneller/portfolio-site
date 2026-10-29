import contextlib
import ftplib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('deploy_reg', Path(__file__).resolve().parents[1] / 'scripts/deploy_reg.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class FakeFTP:
    def __init__(self, missing_root=False, fail_upload=False):
        self.cwd_path = ''
        self.uploads = []
        self.renames = []
        self.missing_root = missing_root
        self.fail_upload = fail_upload

    def cwd(self, path):
        if self.missing_root:
            raise ftplib.error_perm('550 Missing folder')
        self.cwd_path = path if path.startswith('/') else self.cwd_path + '/' + path

    def voidcmd(self, command):
        pass

    def size(self, name):
        if name == 'index.html' or name.endswith('.123456abcdef.webp'):
            return 4
        raise ftplib.error_perm('550 Missing file')

    def storbinary(self, command, stream):
        self.uploads.append((self.cwd_path, command, stream.read()))
        if self.fail_upload:
            raise OSError('Connection lost')

    def retrbinary(self, command, callback):
        callback(b'# Hosting rules\nRewriteEngine On\n')

    def rename(self, source, target):
        self.renames.append((source, target))


class PublishSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.build = Path(self.temp.name)
        for name in ['index.html', 'case01/index.html', 'case02/index.html', 'case03/index.html',
                     'src/main.js', '.htaccess', 'static/case01/original.png',
                     'static/optimized/case01/image.123456abcdef.webp']:
            file = self.build / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b'new!')
        (self.build / 'static/optimized/manifest.json').write_text(json.dumps({
            '/static/case01/original.png': {'src': '/static/optimized/case01/image.123456abcdef.webp'}
        }))
        (self.build / '.htaccess').write_bytes(b'# BEGIN portfolio cache\nCache rules\n# END portfolio cache\n')

    def publish(self, ftp):
        with contextlib.redirect_stdout(io.StringIO()):
            publisher.deploy(ftp, self.build, '/www/efferneller.ru')

    def test_preserves_host_configuration_and_skips_originals_and_existing_hashes(self):
        ftp = FakeFTP()
        self.publish(ftp)
        names = [target for _, target in ftp.renames]
        self.assertEqual(names.count('.htaccess'), 1)
        config = next(data for _, command, data in ftp.uploads if command == 'STOR .htaccess.deploying')
        self.assertTrue(config.startswith(b'# Hosting rules\nRewriteEngine On\n'))
        self.assertNotIn('original.png', names)
        self.assertNotIn('image.123456abcdef.webp', names)
        self.assertIn('main.js', names)  # Same-size mutable files still update.
        html = [i for i, name in enumerate(names) if name.endswith('.html')]
        assets = [i for i, name in enumerate(names) if not name.endswith('.html')]
        self.assertLess(max(assets), min(html))

    def test_wrong_root_stops_before_any_upload(self):
        ftp = FakeFTP(missing_root=True)
        with self.assertRaises(ftplib.error_perm):
            self.publish(ftp)
        self.assertEqual(ftp.uploads, [])

    def test_incomplete_build_stops_before_any_upload(self):
        (self.build / 'case03/index.html').unlink()
        ftp = FakeFTP()
        with self.assertRaises(ValueError):
            self.publish(ftp)
        self.assertEqual(ftp.uploads, [])

    def test_failed_transfer_preserves_published_file_and_stops_before_pages(self):
        ftp = FakeFTP(fail_upload=True)
        with self.assertRaises(OSError):
            self.publish(ftp)
        self.assertEqual(ftp.renames, [])
        self.assertFalse(any('.html' in command for _, command, _ in ftp.uploads))

    def test_tls_failure_stops_before_sending_credentials(self):
        with mock.patch.dict(publisher.os.environ, {'REG_FTP_PASSWORD': 'test-only'}, clear=True), \
                mock.patch.object(publisher, 'build_files'), \
                mock.patch.object(publisher, 'HostingFTP') as client:
            ftp = client.return_value.__enter__.return_value
            ftp.auth.side_effect = publisher.ssl.SSLError('Certificate rejected')
            with self.assertRaises(publisher.ssl.SSLError):
                publisher.main()
            ftp.login.assert_not_called()

    def test_cache_update_preserves_host_rules_and_is_idempotent(self):
        old = b'RewriteEngine On\n# BEGIN portfolio cache\nold\n# END portfolio cache\nSSL rules\n'
        config = b'# BEGIN portfolio cache\nnew\n# END portfolio cache\n'
        updated = publisher.merge_cache(old, config)
        self.assertEqual(updated, b'RewriteEngine On\n' + config + b'SSL rules\n')
        self.assertEqual(publisher.merge_cache(updated, config), updated)

    def test_incomplete_cache_markers_are_not_overwritten(self):
        with self.assertRaises(ValueError):
            publisher.merge_cache(b'# BEGIN portfolio cache\ncustom', (self.build / '.htaccess').read_bytes())


if __name__ == '__main__':
    unittest.main()
