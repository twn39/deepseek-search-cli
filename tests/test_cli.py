import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from deepseek_search_cli import __version__
from deepseek_search_cli.cli import app
from deepseek_search_cli.models import FetchResponse, SearchResponse, SearchResult

runner = CliRunner()


class TestCLI(unittest.TestCase):
    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(__version__, result.stdout)

    @patch("deepseek_search_cli.client.resolve_api_key", return_value="")
    def test_missing_api_key_error(self, mock_resolve):
        result = runner.invoke(app, ["search", "hello"], env={"DEEPSEEK_API_KEY": ""})
        self.assertEqual(result.exit_code, 1)
        self.assertIn("API Key 未提供", result.output)

    @patch("deepseek_search_cli.cli.DeepSeekClient")
    def test_search_command_json_format(self, mock_client_cls):
        mock_instance = mock_client_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    rerank_score=2.5,
                    title="DeepSeek API 官方指南",
                    url="https://api-docs.deepseek.com",
                    snippet="DeepSeek 网页搜索接口文档",
                    summary="DeepSeek 搜索与抓取详细指南",
                    authority=3,
                )
            ]
        )

        result = runner.invoke(
            app,
            [
                "search",
                "DeepSeek API",
                "--count",
                "5",
                "--format",
                "json",
                "--api-key",
                "sk-dummy",
            ],
        )

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["title"], "DeepSeek API 官方指南")
        mock_instance.search.assert_called_once_with(
            query="DeepSeek API",
            count=5,
            need_content=False,
            ori_question=None,
            localization=None,
        )

    @patch("deepseek_search_cli.cli.DeepSeekClient")
    def test_search_command_default_format_is_markdown(self, mock_client_cls):
        mock_instance = mock_client_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    rerank_score=2.5,
                    title="DeepSeek API 官方指南",
                    url="https://api-docs.deepseek.com",
                    snippet="DeepSeek 网页搜索接口文档",
                    summary="DeepSeek 搜索与抓取详细指南",
                    authority=3,
                )
            ]
        )

        result = runner.invoke(app, ["search", "DeepSeek API", "--api-key", "sk-dummy"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("# 搜索结果 (共 1 条)", result.stdout)
        self.assertIn(
            "## 1. [DeepSeek API 官方指南](https://api-docs.deepseek.com)",
            result.stdout,
        )

    @patch("deepseek_search_cli.cli.DeepSeekClient")
    def test_search_syntax_helpers(self, mock_client_cls):
        mock_instance = mock_client_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.search.return_value = SearchResponse(results=[])

        result = runner.invoke(
            app,
            [
                "search",
                "开源模型",
                "--site",
                "github.com",
                "--exclude-site",
                "spam.com",
                "--lang",
                "zh",
                "--after",
                "2025",
                "--api-key",
                "sk-dummy",
            ],
        )

        self.assertEqual(result.exit_code, 0)
        mock_instance.search.assert_called_once_with(
            query="开源模型 site:github.com -site:spam.com lang:zh after:2025",
            count=10,
            need_content=False,
            ori_question=None,
            localization=None,
        )

    @patch("deepseek_search_cli.cli.DeepSeekClient")
    def test_search_output_file(self, mock_client_cls):
        mock_instance = mock_client_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    rerank_score=1.8,
                    title="测试结果",
                    url="https://example.com",
                    snippet="测试摘要",
                    summary="长测试摘要",
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "search_result.json"
            result = runner.invoke(
                app,
                [
                    "search",
                    "测试",
                    "--format",
                    "json",
                    "--output",
                    str(out_file),
                    "--api-key",
                    "sk-dummy",
                ],
            )

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(out_file.exists())
            saved_data = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(len(saved_data["results"]), 1)

    @patch("deepseek_search_cli.cli.DeepSeekClient")
    def test_fetch_command(self, mock_client_cls):
        mock_instance = mock_client_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.fetch.return_value = FetchResponse(
            title="测试抓取页面",
            content="# 标题\n\n正文抓取成功",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "page.md"
            result = runner.invoke(
                app,
                [
                    "fetch",
                    "https://example.com/test",
                    "--format",
                    "raw",
                    "--output",
                    str(out_file),
                    "--api-key",
                    "sk-dummy",
                ],
            )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("# 标题", result.stdout)
            self.assertTrue(out_file.exists())
            self.assertIn("正文抓取成功", out_file.read_text(encoding="utf-8"))
            mock_instance.fetch.assert_called_once_with(url="https://example.com/test")

    @patch("deepseek_search_cli.cli.DeepSeekClient")
    def test_search_with_fetch_top(self, mock_client_cls):
        mock_instance = mock_client_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    rerank_score=2.8,
                    title="结果1",
                    url="https://example.com/1",
                    snippet="短摘",
                    summary="长摘",
                )
            ]
        )
        mock_instance.fetch.return_value = FetchResponse(
            title="结果1详情",
            content="# 深度全文内容",
        )

        result = runner.invoke(
            app,
            [
                "search",
                "AI",
                "--fetch-top",
                "1",
                "--format",
                "markdown",
                "--api-key",
                "sk-dummy",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("# 深度全文内容", result.stdout)
        mock_instance.fetch.assert_called_once_with("https://example.com/1")

    @patch("deepseek_search_cli.cli.DeepSeekClient")
    def test_fetch_stdin_pipe(self, mock_client_cls):
        mock_instance = mock_client_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.fetch.return_value = FetchResponse(
            title="管道抓取",
            content="# 管道正文",
        )
        mock_instance.fetch_many.side_effect = lambda urls, max_workers=5: [
            (u, mock_instance.fetch(u)) for u in urls
        ]
        mock_instance.fetch_many.side_effect = lambda urls, max_workers=5: [
            (u, mock_instance.fetch(u)) for u in urls
        ]

        result = runner.invoke(
            app,
            ["fetch", "-", "--format", "raw", "--api-key", "sk-dummy"],
            input="https://example.com/pipe1\nhttps://example.com/pipe2\n",
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("# 管道正文", result.stdout)
        self.assertEqual(mock_instance.fetch.call_count, 2)

    def test_config_show(self):
        result = runner.invoke(app, ["config", "show"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("全局配置文件路径", result.output)

    def test_config_path(self):
        result = runner.invoke(app, ["config", "path"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("config.json", result.output)

    @patch(
        "deepseek_search_cli.cli.DeepSeekClient.verify",
        return_value=(True, "Key 验证通过"),
    )
    @patch("deepseek_search_cli.cli.save_file_config")
    def test_config_login_command(self, mock_save, mock_verify):
        result = runner.invoke(app, ["config", "login", "sk-custom123"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("已保存至全局配置", result.output)
        mock_save.assert_called_once_with({"api_key": "sk-custom123"})

    @patch(
        "deepseek_search_cli.cli.get_api_key_source",
        return_value=("sk-mock12345678", "全局配置"),
    )
    @patch("deepseek_search_cli.cli.DeepSeekClient.verify", return_value=(True, "凭证有效"))
    def test_config_status_command(self, mock_verify, mock_source):
        result = runner.invoke(app, ["config", "status"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("DeepSeek 认证与配置状态", result.output)
        self.assertIn("sk-mock...5678", result.output)
        self.assertIn("有效", result.output)

    @patch("deepseek_search_cli.cli.save_local_env")
    def test_config_login_local(self, mock_save_local):
        result = runner.invoke(app, ["config", "login", "sk-local789", "--local", "--no-check"])
        self.assertEqual(result.exit_code, 0)
        mock_save_local.assert_called_once_with(api_key="sk-local789", base_url=None)

    @patch("deepseek_search_cli.cli.load_file_config", return_value={"api_key": "sk-del"})
    @patch("deepseek_search_cli.cli.get_config_file")
    def test_config_logout(self, mock_get_cfg, mock_load):
        mock_file = MagicMock()
        mock_get_cfg.return_value = mock_file
        result = runner.invoke(app, ["config", "logout"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("已清除", result.output)

    @patch("deepseek_search_cli.cli.DeepSeekClient")
    def test_search_command_urls_format(self, mock_client_cls):
        mock_instance = mock_client_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    rerank_score=2.0,
                    title="结果1",
                    url="https://example.com/item1",
                    snippet="",
                    summary="",
                ),
                SearchResult(
                    rerank_score=1.8,
                    title="结果2",
                    url="https://example.com/item2",
                    snippet="",
                    summary="",
                ),
            ]
        )

        result = runner.invoke(
            app,
            ["search", "测试", "--format", "urls", "--api-key", "sk-dummy"],
        )
        self.assertEqual(result.exit_code, 0)
        expected_output = "https://example.com/item1\nhttps://example.com/item2\n"
        self.assertEqual(result.stdout, expected_output)

    def test_search_query_too_long(self):
        result = runner.invoke(
            app,
            [
                "search",
                "a" * 120,
                "--site",
                "very-long-domain-name-that-definitely-exceeds-the-limit.com",
            ],
        )
        self.assertEqual(result.exit_code, 1)
        self.assertIn("超过 DeepSeek 128 字符上限", result.output)

    @patch("deepseek_search_cli.cli.DeepSeekClient")
    def test_search_with_fetch_top_multi(self, mock_client_cls):
        mock_instance = mock_client_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.search.return_value = SearchResponse(
            results=[
                SearchResult(
                    rerank_score=2.8,
                    title="结果1",
                    url="https://example.com/1",
                    snippet="",
                    summary="",
                ),
                SearchResult(
                    rerank_score=2.5,
                    title="结果2",
                    url="https://example.com/2",
                    snippet="",
                    summary="",
                ),
            ]
        )
        mock_instance.fetch_many.return_value = [
            ("https://example.com/1", FetchResponse(title="详情1", content="正文1")),
            ("https://example.com/2", FetchResponse(title="详情2", content="正文2")),
        ]

        result = runner.invoke(
            app,
            ["search", "test", "--fetch-top", "2", "--format", "json", "--api-key", "sk-dummy"],
        )
        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["results"][0]["content"], "正文1")
        self.assertEqual(data["results"][1]["content"], "正文2")
        mock_instance.fetch_many.assert_called_once_with(
            ["https://example.com/1", "https://example.com/2"],
            max_workers=5,
        )


if __name__ == "__main__":
    unittest.main()
