import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pack


class InitializeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'Demo.csproj'
        self.source = '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><Version>1.0</Version></PropertyGroup></Project>'
        self.project.write_text(self.source)
        for patcher in (
            mock.patch.object(pack, 'ROOT', self.root),
            mock.patch.object(pack, 'CFG_PATH', self.root / 'packaging.json'),
            mock.patch.object(pack, 'load_preferences', return_value={}),
            mock.patch.object(pack, 'default_publisher_url', return_value='https://example.com'),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_platforms_use_shared_templates_and_matching_workflow(self):
        for platform in ('windows', 'macos', 'both'):
            with self.subTest(platform=platform):
                pack.initialize('Demo.csproj', platform, '1.1')
                cfg = json.loads((self.root / 'packaging.json').read_text())
                workflow = (self.root / '.github/workflows/installers.yml').read_text()
                self.assertEqual(platform == 'windows', cfg['Mac'] is None)
                self.assertEqual(platform == 'macos', cfg['Win'] is None)
                if cfg['Win']:
                    self.assertEqual('Installer/templates/inno.iss', cfg['Win']['InnoScript'])
                self.assertIn('build_windows: ' + str(platform != 'macos').lower(), workflow)
                self.assertIn('build_macos: ' + str(platform != 'windows').lower(), workflow)
                self.assertIn('default: "1.1"', workflow)
                self.assertIn('${{ inputs.version }}', workflow)
                self.assertEqual(self.source, self.project.read_text())
                original = (self.root / 'packaging.json').read_bytes()
                with self.assertRaises(pack.PackagingError):
                    pack.initialize('Demo.csproj', platform, '1.2')
                self.assertEqual(original, (self.root / 'packaging.json').read_bytes())
                (self.root / 'packaging.json').unlink()
                (self.root / '.github/workflows/installers.yml').unlink()

    def test_existing_workflow_prevents_partial_setup(self):
        workflow = self.root / '.github/workflows/installers.yml'
        workflow.parent.mkdir(parents=True)
        workflow.write_text('existing workflow')
        with self.assertRaises(pack.PackagingError):
            pack.initialize('Demo.csproj', 'windows', '1.1')
        self.assertFalse((self.root / 'packaging.json').exists())
        self.assertEqual('existing workflow', workflow.read_text())

    def test_classic_project_rejected_without_writing_files(self):
        self.project.write_text('<Project ToolsVersion="15.0" />')
        with self.assertRaisesRegex(pack.PackagingError, 'SDK-style'):
            pack.initialize('Demo.csproj', 'windows', '1.1')
        self.assertFalse((self.root / 'packaging.json').exists())
