from __future__ import annotations

import concurrent.futures
import json
import os
import random
import re
import time
from collections.abc import Sequence
from typing import Any, Self

import httpx

from deepseek_search_cli.config import (
    DEFAULT_BASE_URL,
    resolve_api_key,
    resolve_base_url,
)
from deepseek_search_cli.models import FetchResponse, SearchResponse

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

STATUS_CODE_MESSAGES: dict[int, str] = {
    400: "请求头或请求体不合法（例如 JSON 格式错误、参数越界或字段值无效）。",
    401: "API Key 缺失或无效，请检查 DEEPSEEK_API_KEY 是否正确。",
    402: "账号余额不足，请前往 DeepSeek 控制台充值后重试。",
    403: "Fetch 请求被目标站点或系统安全策略拒绝。",
    404: "Fetch 未能获取可用的网页内容（URL 不可用、被拦截、不受支持或无 Markdown 正文）。",
    408: "读取请求体超时，请稍后重试。",
    413: "请求体超过大小限制。",
    429: "超过 QPS 限制（Search 限制 100 QPS，Fetch 限制 25 QPS 或目标域名限速），请降低并发稍后重试。",
    500: "DeepSeek 服务器内部错误，请稍后重试。",
    504: "下游请求超时，请稍后重试。",
}


class DeepSeekAPIError(Exception):
    """Raised when DeepSeek API returns an error response."""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_type: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.error_type = error_type
        self.error_code = error_code
        doc_hint = STATUS_CODE_MESSAGES.get(status_code, "请检查请求与服务状态。")
        super().__init__(f"[{status_code}] {message} ({doc_hint})")


def normalize_url(url: str) -> str:
    """Normalize and validate a URL for DeepSeek Fetch API.

    - Strips leading/trailing whitespace.
    - Prepends 'https://' if the URL scheme is omitted (e.g. 'github.com/foo' -> 'https://github.com/foo').
    - Enforces length limit (<= 8192 chars) and HTTP/HTTPS host validity without user/password.
    """
    clean_url = url.strip()
    if not clean_url:
        raise ValueError("抓取网页 url 不能为空。")
    if len(clean_url) > 8192:
        raise ValueError(f"url 长度超过 8192 个字符（当前 {len(clean_url)} 个字符）。")

    if not clean_url.startswith(("http://", "https://")):
        clean_url = f"https://{clean_url}"

    if not re.match(r"^https?://([^/@:]+)(:\d+)?(/.*)?$", clean_url):
        raise ValueError("url 必须为含 host 的合法 HTTP/HTTPS URL，且不能包含用户名或密码。")

    return clean_url


class DeepSeekClient:
    """Client for DeepSeek Search & Fetch APIs using httpx."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = resolve_api_key(api_key)
        self.base_url = resolve_base_url(base_url)
        self.timeout = timeout
        self.max_retries = max(0, max_retries)

        if not self.api_key:
            raise ValueError(
                "DeepSeek API Key 未提供。请设置环境变量 DEEPSEEK_API_KEY、使用 --api-key 参数，或运行 'deepseek-search config set --api-key <key>' 保存配置。"
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "deepseek-search-cli/1.0.0",
        }

        if client is not None:
            self._client = client
            for k, v in headers.items():
                if k not in self._client.headers:
                    self._client.headers[k] = v
        else:
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        self._owns_client = client is None

    @staticmethod
    def verify(api_key: str, base_url: str | None = None) -> tuple[bool, str]:
        """Verify if the API key is valid by sending a test request."""
        clean_key = api_key.strip()
        if not clean_key:
            return False, "API Key 为空。"
        target_url = (base_url or os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        headers = {
            "Authorization": f"Bearer {clean_key}",
            "Content-Type": "application/json",
            "User-Agent": "deepseek-search-cli/1.0.0",
        }
        try:
            with httpx.Client(base_url=target_url, headers=headers, timeout=10.0) as client:
                resp = client.post("/v1/tools/search", json={"query": "ping", "count": 1})
                if resp.status_code == 200:
                    return True, "API Key 校验成功，凭证有效！"
                elif resp.status_code == 402:
                    return True, "API Key 鉴权通过（但当前账号余额不足）。"
                elif resp.status_code == 401:
                    return False, "API Key 鉴权失败：密钥不存在或已失效。"
                else:
                    return False, f"API 返回状态码 HTTP {resp.status_code}：{resp.text}"
        except (httpx.HTTPError, OSError) as e:
            return False, f"连接 DeepSeek API 超时或出错：{e}"

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _post_with_retry(self, path: str, json_payload: dict[str, Any]) -> httpx.Response:
        """Send POST request with lightweight exponential backoff for transient idempotent errors."""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            resp: httpx.Response | None = None
            try:
                resp = self._client.post(path, json=json_payload)
                if resp.status_code not in RETRYABLE_STATUS_CODES or attempt == self.max_retries:
                    return resp
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_exc = e
                if attempt == self.max_retries:
                    raise

            # Exponential backoff with jitter (e.g. 0.5s -> 1.0s -> ...)
            backoff = (0.5 * (2**attempt)) + random.uniform(0.05, 0.25)
            if resp is not None and resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                if retry_after:
                    try:
                        backoff = max(float(retry_after), backoff)
                    except ValueError:
                        pass
            time.sleep(backoff)

        if last_exc:
            raise last_exc
        if resp is None:
            raise RuntimeError("请求未执行或未能获取响应。")
        return resp

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse response and handle API errors."""
        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError):
            data = None

        if response.is_error:
            msg = response.text
            err_type = None
            err_code = None
            if isinstance(data, dict) and "error" in data:
                err_info = data["error"]
                if isinstance(err_info, dict):
                    msg = err_info.get("message", msg)
                    err_type = err_info.get("type")
                    err_code = err_info.get("code")

            raise DeepSeekAPIError(
                status_code=response.status_code,
                message=msg,
                error_type=err_type,
                error_code=err_code,
            )

        if not isinstance(data, dict):
            raise DeepSeekAPIError(
                status_code=response.status_code,
                message="DeepSeek API 返回了非 JSON 对象数据。",
            )

        return data

    def search(
        self,
        query: str,
        *,
        count: int = 10,
        need_content: bool = False,
        ori_question: str | None = None,
        localization: str | None = None,
    ) -> SearchResponse:
        """Search web using DeepSeek Search API (POST /v1/tools/search).

        Args:
            query: 搜索词，1～128 个字符，支持高级搜索语法
            count: 返回结果条数 (1～50，默认 10)
            need_content: 是否在 content 中返回网页正文 (默认 False)
            ori_question: 触发搜索的用户原始问题 (1～128 个字符)
            localization: 本地化搜索 IP 地址
        """
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("搜索关键词 query 不能为空或全为空白。")
        if len(clean_query) > 128:
            raise ValueError(
                f"搜索关键词 query 长度超过 128 个字符（当前 {len(clean_query)} 个字符）。"
            )
        if not (1 <= count <= 50):
            raise ValueError(f"count 参数必须在 1 到 50 之间（当前值为 {count}）。")

        payload: dict[str, Any] = {
            "query": clean_query,
            "count": count,
            "need_content": need_content,
        }
        if ori_question is not None:
            clean_q = ori_question.strip()
            if clean_q:
                if len(clean_q) > 128:
                    raise ValueError(
                        f"原始问题 ori_question 长度超过 128 个字符（当前 {len(clean_q)} 个字符）。"
                    )
                payload["ori_question"] = clean_q
            else:
                payload["ori_question"] = None

        if localization is not None and localization.strip():
            payload["localization"] = localization.strip()

        resp = self._post_with_retry("/v1/tools/search", json_payload=payload)
        data = self._handle_response(resp)
        return SearchResponse.from_dict(data)

    def fetch(self, url: str) -> FetchResponse:
        """Fetch a webpage using DeepSeek Fetch API (POST /v1/tools/fetch).

        Args:
            url: 要抓取的网页地址，含 host 的 HTTP/HTTPS URL (若省略协议会自动补齐 https://)。
        """
        clean_url = normalize_url(url)
        payload = {"url": clean_url}
        resp = self._post_with_retry("/v1/tools/fetch", json_payload=payload)
        data = self._handle_response(resp)
        return FetchResponse.from_dict(data)

    def fetch_many(
        self,
        urls: Sequence[str],
        max_workers: int = 5,
    ) -> list[tuple[str, FetchResponse | Exception]]:
        """Fetch multiple webpages concurrently using a lightweight thread pool.

        Maintains the exact original order of URLs in the returned list.
        Each element is a tuple of (clean_url, FetchResponse or Exception).

        Args:
            urls: 要抓取的网页地址列表。
            max_workers: 最大并发抓取线程数 (默认 5，建议不超过 DeepSeek 25 QPS 阈值)。
        """
        if not urls:
            return []

        url_list = list(urls)
        placeholder_err = RuntimeError("未完成抓取")
        results: list[tuple[str, FetchResponse | Exception]] = [
            ("", placeholder_err) for _ in url_list
        ]

        def _worker(idx: int, target_url: str) -> None:
            clean = target_url.strip()
            try:
                res = self.fetch(clean)
                results[idx] = (normalize_url(clean), res)
            except Exception as exc:  # noqa: BLE001
                results[idx] = (clean, exc)

        workers = min(max(1, max_workers), len(url_list))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_worker, i, u) for i, u in enumerate(url_list)]
            concurrent.futures.wait(futures)

        return results
