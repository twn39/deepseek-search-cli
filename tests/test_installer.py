import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from deepseek_search_cli.cli import app
from deepseek_search_cli.installer import (
    _get_skill_source_path,
    get_target_destinations,
)

runner = CliRunner()


class TestSkillsInstaller(unittest.TestCase):
    def test_get_skill_source_path(self):
        skill_path = _get_skill_source_path()
        self.assertTrue(skill_path.is_file())
        self.assertEqual(skill_path.name, "SKILL.md")
        content = skill_path.read_text(encoding="utf-8")
        self.assertIn("name: deepseek-search", content)

    def test_get_target_destinations_global(self):
        fake_home = Path("/fake/home")
        dests = get_target_destinations(
            ["antigravity", "claude", "cursor", "codex", "crush"],
            global_install=True,
            home_dir=fake_home,
        )
        self.assertEqual(len(dests), 5)
        paths_str = [str(p) for _, p in dests]
        self.assertTrue(any(".gemini/config/skills" in p for p in paths_str))
        self.assertTrue(any(".claude/skills" in p for p in paths_str))
        self.assertTrue(any(".cursor/skills" in p for p in paths_str))
        self.assertTrue(any(".codex/skills" in p for p in paths_str))
        self.assertTrue(any(".config/crush/skills" in p for p in paths_str))

    def test_get_target_destinations_local(self):
        fake_cwd = Path("/fake/project")
        dests = get_target_destinations(
            ["antigravity", "claude"],
            global_install=False,
            cwd_dir=fake_cwd,
        )
        self.assertEqual(len(dests), 2)
        paths_str = [str(p) for _, p in dests]
        self.assertTrue(any(".agents/skills" in p for p in paths_str))
        self.assertTrue(any(".claude/skills" in p for p in paths_str))

    def test_install_skills_command_local(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_cwd = Path(tmpdir)
            with patch("pathlib.Path.cwd", return_value=temp_cwd):
                result = runner.invoke(
                    app,
                    ["skills", "install", "--local", "--target", "claude,cursor"],
                )
                self.assertEqual(result.exit_code, 0)
                self.assertIn("成功为 2 个 AI Agent 平台安装", result.output)
                claude_skill = temp_cwd / ".claude" / "skills" / "deepseek-search" / "SKILL.md"
                cursor_skill = temp_cwd / ".cursor" / "skills" / "deepseek-search" / "SKILL.md"
                self.assertTrue(claude_skill.is_file())
                self.assertTrue(cursor_skill.is_file())
                self.assertIn("name: deepseek-search", claude_skill.read_text(encoding="utf-8"))

    def test_install_skill_alias(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_cwd = Path(tmpdir)
            with patch("pathlib.Path.cwd", return_value=temp_cwd):
                result = runner.invoke(
                    app,
                    ["install-skill", "--local", "--target", "antigravity"],
                )
                self.assertEqual(result.exit_code, 0)
                self.assertIn("成功为 1 个 AI Agent 平台安装", result.output)
                skill_file = temp_cwd / ".agents" / "skills" / "deepseek-search" / "SKILL.md"
                self.assertTrue(skill_file.is_file())

    def test_install_skills_invalid_target(self):
        result = runner.invoke(app, ["skills", "install", "--target", "invalid_platform"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("无效的平台目标", result.output)


if __name__ == "__main__":
    unittest.main()
