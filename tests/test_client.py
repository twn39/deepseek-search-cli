import json
import unittest
from unittest.mock import patch

import httpx

from deepseek_search_cli.client import (
    DeepSeekAPIError,
    DeepSeekClient,
    normalize_url,
)
from deepseek_search_cli.models import FetchResponse


class TestDeepSeekClient(unittest.TestCase):
    @patch("deepseek_search_cli.client.resolve_api_key", return_value="")
    def test_missing_api_key_raises_error(self, mock_resolve):
        with self.assertRaises(ValueError) as ctx:
            DeepSeekClient(api_key="")
        self.assertIn("API Key 未提供", str(ctx.exception))

    def test_search_validation_empty_query(self):
        client = DeepSeekClient(api_key="sk-test")
        with self.assertRaises(ValueError) as ctx:
            client.search("   ")
        self.assertIn("不能为空或全为空白", str(ctx.exception))

    def test_search_validation_long_query(self):
        client = DeepSeekClient(api_key="sk-test")
        with self.assertRaises(ValueError) as ctx:
            client.search("a" * 129)
        self.assertIn("长度超过 128", str(ctx.exception))

    def test_search_validation_count_range(self):
        client = DeepSeekClient(api_key="sk-test")
        with self.assertRaises(ValueError):
            client.search("test", count=0)
        with self.assertRaises(ValueError):
            client.search("test", count=51)

    def test_search_validation_ori_question(self):
        client = DeepSeekClient(api_key="sk-test")
        with self.assertRaises(ValueError):
            client.search("test", ori_question="q" * 129)

    def test_fetch_validation(self):
        client = DeepSeekClient(api_key="sk-test")
        with self.assertRaises(ValueError):
            client.fetch("")
        with self.assertRaises(ValueError):
            client.fetch("ftp://example.com")
        with self.assertRaises(ValueError):
            client.fetch("https://user:pass@example.com")

    def test_search_success_mock(self):
        mock_response_data = {
            "results": [
                {
                    "rerank_score": 2.4,
                    "title": "DeepSeek V4 模型发布",
                    "url": "https://example.com/deepseek-v4",
                    "snippet": "DeepSeek V4 已上线",
                    "summary": "DeepSeek 发布了 V4 模型",
                    "content": "正文内容",
                    "site_name": "Example News",
                    "site_icon": "https://example.com/icon.ico",
                    "date": "2026-06-01T00:00:00+00:00",
                    "authority": 3,
                }
            ]
        }

        def mock_transport(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/v1/tools/search")
            self.assertEqual(request.headers.get("authorization"), "Bearer sk-test")
            body = json.loads(request.content)
            self.assertEqual(body["query"], "DeepSeek V4")
            self.assertEqual(body["count"], 5)
            self.assertTrue(body["need_content"])
            return httpx.Response(200, json=mock_response_data)

        transport = httpx.MockTransport(mock_transport)
        with httpx.Client(transport=transport, base_url="https://api.deepseek.com") as http_client:
            client = DeepSeekClient(api_key="sk-test", client=http_client)
            res = client.search("DeepSeek V4", count=5, need_content=True)

            self.assertEqual(len(res.results), 1)
            item = res.results[0]
            self.assertEqual(item.title, "DeepSeek V4 模型发布")
            self.assertEqual(item.rerank_score, 2.4)
            self.assertTrue(item.is_high_quality)
            self.assertTrue(item.is_highly_authoritative)

    def test_fetch_success_mock(self):
        mock_response_data = {
            "title": "DeepSeek 官方文档",
            "content": "# DeepSeek 官方文档\n\n欢迎使用！",
        }

        def mock_transport(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/v1/tools/fetch")
            self.assertEqual(request.headers.get("authorization"), "Bearer sk-test")
            body = json.loads(request.content)
            self.assertEqual(body["url"], "https://example.com/doc")
            return httpx.Response(200, json=mock_response_data)

        transport = httpx.MockTransport(mock_transport)
        with httpx.Client(transport=transport, base_url="https://api.deepseek.com") as http_client:
            client = DeepSeekClient(api_key="sk-test", client=http_client)
            res = client.fetch("https://example.com/doc")

            self.assertEqual(res.title, "DeepSeek 官方文档")
            self.assertIn("# DeepSeek 官方文档", res.content)

    def test_error_handling_mock(self):
        def mock_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                json={
                    "error": {
                        "message": "Authentication Fails (no such user)",
                        "type": "authentication_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            )

        transport = httpx.MockTransport(mock_transport)
        with httpx.Client(transport=transport, base_url="https://api.deepseek.com") as http_client:
            client = DeepSeekClient(api_key="sk-bad", client=http_client)
            with self.assertRaises(DeepSeekAPIError) as ctx:
                client.search("test")

            err = ctx.exception
            self.assertEqual(err.status_code, 401)
            self.assertIn("Authentication Fails", err.message)
            self.assertEqual(err.error_code, "invalid_api_key")

    def test_retry_mechanism_on_transient_error(self):
        calls = 0

        def mock_transport(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(429, json={"error": {"message": "Rate limit exceeded"}})
            return httpx.Response(200, json={"results": []})

        transport = httpx.MockTransport(mock_transport)
        with httpx.Client(transport=transport, base_url="https://api.deepseek.com") as http_client:
            client = DeepSeekClient(api_key="sk-test", client=http_client, max_retries=1)
            res = client.search("test")
            self.assertEqual(len(res.results), 0)
            self.assertEqual(calls, 2)

    def test_normalize_url(self):
        self.assertEqual(normalize_url("example.com"), "https://example.com")
        self.assertEqual(normalize_url("example.com/doc"), "https://example.com/doc")
        self.assertEqual(normalize_url("http://example.com"), "http://example.com")
        self.assertEqual(normalize_url("https://example.com"), "https://example.com")
        with self.assertRaises(ValueError):
            normalize_url("")
        with self.assertRaises(ValueError):
            normalize_url("   ")
        with self.assertRaises(ValueError):
            normalize_url("ftp://example.com")
        with self.assertRaises(ValueError):
            normalize_url("https://user:pass@example.com")

    def test_fetch_many_success_and_order(self):
        def mock_transport(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            url = body["url"]
            return httpx.Response(
                200,
                json={"title": f"Title for {url}", "content": f"Content for {url}"},
            )

        transport = httpx.MockTransport(mock_transport)
        with httpx.Client(transport=transport, base_url="https://api.deepseek.com") as http_client:
            client = DeepSeekClient(api_key="sk-test", client=http_client)
            urls = [
                "https://example.com/1",
                "example.com/2",
                "https://example.com/3",
            ]
            results = client.fetch_many(urls, max_workers=3)
            self.assertEqual(len(results), 3)
            self.assertEqual(results[0][0], "https://example.com/1")
            self.assertEqual(results[1][0], "https://example.com/2")
            self.assertEqual(results[2][0], "https://example.com/3")
            r0 = results[0][1]
            r1 = results[1][1]
            r2 = results[2][1]
            assert isinstance(r0, FetchResponse)
            assert isinstance(r1, FetchResponse)
            assert isinstance(r2, FetchResponse)
            self.assertEqual(r0.title, "Title for https://example.com/1")
            self.assertEqual(r1.title, "Title for https://example.com/2")
            self.assertEqual(r2.title, "Title for https://example.com/3")

    def test_fetch_many_isolated_errors(self):
        def mock_transport(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            url = body["url"]
            if "fail" in url:
                return httpx.Response(404, json={"error": {"message": "Not found"}})
            return httpx.Response(200, json={"title": "Success", "content": "OK"})

        transport = httpx.MockTransport(mock_transport)
        with httpx.Client(transport=transport, base_url="https://api.deepseek.com") as http_client:
            client = DeepSeekClient(api_key="sk-test", client=http_client, max_retries=0)
            urls = ["https://example.com/ok", "https://example.com/fail"]
            results = client.fetch_many(urls, max_workers=2)
            self.assertEqual(len(results), 2)
            self.assertIsInstance(results[0][1], FetchResponse)
            self.assertIsInstance(results[1][1], DeepSeekAPIError)

    def test_retry_after_header_handling(self):
        calls = 0

        def mock_transport(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0.01"},
                    json={"error": {"message": "Rate limit exceeded"}},
                )
            return httpx.Response(200, json={"results": []})

        transport = httpx.MockTransport(mock_transport)
        with httpx.Client(transport=transport, base_url="https://api.deepseek.com") as http_client:
            client = DeepSeekClient(api_key="sk-test", client=http_client, max_retries=1)
            res = client.search("test")
            self.assertEqual(len(res.results), 0)
            self.assertEqual(calls, 2)


if __name__ == "__main__":
    unittest.main()
