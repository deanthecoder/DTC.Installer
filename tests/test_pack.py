import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pack


class CommandLineConfigTests(unittest.TestCase):
    def test_missing_command_line_returns_none(self):
        self.assertIsNone(pack.command_line_name({"Executable": "app"}))

    def test_true_uses_executable_without_extension(self):
        self.assertEqual("brain", pack.command_line_name({"Executable": "brain.exe", "CommandLine": True}))

    def test_object_uses_explicit_name(self):
        self.assertEqual("remember", pack.command_line_name({"Executable": "brain", "CommandLine": {"Name": "remember"}}))

    def test_invalid_name_raises(self):
        with self.assertRaises(pack.PackagingError):
            pack.command_line_name({"Executable": "brain", "CommandLine": {"Name": "brain tool"}})

    def test_macos_package_places_payload_and_command_link(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            publish_dir = root / "publish"
            publish_dir.mkdir()
            executable = publish_dir / "brain"
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

            with mock.patch.object(pack, "ROOT", root), \
                 mock.patch.object(pack, "WORK_ROOT", root / ".work"), \
                 mock.patch.object(pack, "sh") as run:
                pack.package_macos_command_line(
                    {"ProductName": "Brain"},
                    {"VolumeName": "Brain"},
                    publish_dir,
                    "1.0",
                    "osx-arm64",
                    "brain",
                    "brain",
                    "com.deanthecoder.brain",
                )

            command = root / ".work" / "mac-osx-arm64" / "payload" / "usr" / "local" / "bin" / "brain"
            self.assertTrue(command.is_symlink())
            self.assertEqual(Path("../lib/brain/brain"), command.readlink())
            self.assertEqual("brain", (root / ".work" / "mac-osx-arm64" / "payload" / "usr" / "local" / "lib" / "brain" / "brain").name)
            self.assertEqual("pkgbuild", run.call_args_list[0].args[0][0])
            self.assertEqual("hdiutil", run.call_args_list[1].args[0][0])

    def test_project_property_preserves_existing_indentation(self):
        project = """<Project Sdk=\"Microsoft.NET.Sdk\">

  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <AssemblyName>brain</AssemblyName>
  </PropertyGroup>

</Project>
"""

        updated = pack.upsert_project_property(project, "Version", "1.2")

        self.assertIn("    <Version>1.2</Version>\n    <AssemblyName>brain</AssemblyName>", updated)

    def test_windows_package_uses_runner_temp_then_copies_installer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            publish_dir = root / "publish"
            publish_dir.mkdir()
            (publish_dir / "brain.exe").touch()
            template = root / "inno.iss"
            template.write_text("{{OutputDir}}\n{{OutputBase}}\n", encoding="utf-8")
            runner_temp = root / "runner-temp"
            cfg = {
                "ProductName": "Brain",
                "Executable": "brain",
                "CommandLine": {"Name": "brain"},
                "Win": {"Executable": "brain.exe", "InnoScript": "inno.iss"},
            }

            def compile_installer(_command):
                output_dir = runner_temp / "dtc-installer-output"
                (output_dir / "Brain-1.0-win-x64.exe").touch()

            with mock.patch.object(pack, "ROOT", root), \
                 mock.patch.object(pack, "WORK_ROOT", root / ".work"), \
                 mock.patch.object(pack, "locate_inno_compiler", return_value="iscc"), \
                 mock.patch.object(pack, "sh", side_effect=compile_installer), \
                 mock.patch.dict(pack.os.environ, {"RUNNER_TEMP": str(runner_temp)}):
                pack.package_windows(cfg, publish_dir, "1.0", "win-x64")

            generated = (root / ".work" / "windows" / "inno_generated.iss").read_text(encoding="utf-8")
            self.assertIn(str(runner_temp / "dtc-installer-output"), generated)
            self.assertTrue((root / "dist" / "win" / "Brain-1.0-win-x64.exe").exists())


if __name__ == "__main__":
    unittest.main()
