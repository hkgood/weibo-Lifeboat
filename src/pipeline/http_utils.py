from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import httpx


class AntiBotTriggered(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpRetryPolicy:
    max_attempts: int = 4
    base_delay: float = 0.2
    jitter: float = 0.6
    backoff_base: float = 3.0
    antibot_statuses: Tuple[int, ...] = (403, 418, 429)


async def get_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: Dict[str, str],
    params: Optional[Dict[str, str]] = None,
    policy: HttpRetryPolicy = HttpRetryPolicy(),
    antibot_fail_fast: bool = True,
) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(1, policy.max_attempts + 1):
        await asyncio.sleep(policy.base_delay + random.random() * policy.jitter)
        try:
            resp = await client.get(url, headers=headers, params=params)
        except Exception as e:
            last_exc = e
            # 有些反爬不是 403，而是直接断连（ConnectError/TLS EOF）。这类继续“死磕重试”只会浪费时间：
            # - 首次 ConnectError 允许继续按退避重试（可能是瞬时网络抖动）
            # - 连续 ConnectError（attempt>=2）或明确 TLS EOF：升级为 AntiBotTriggered 让上层进入冷却
            if isinstance(e, httpx.ConnectError):
                msg = str(e) or ""
                is_tls_eof = "EOF occurred in violation of protocol" in msg
                if antibot_fail_fast and (is_tls_eof or attempt >= 2):
                    raise AntiBotTriggered(
                        f"anti-bot connect_error url={url} attempt={attempt} exc={type(e).__name__}({e!r})"
                    )
            backoff = policy.backoff_base * (2 ** (attempt - 1)) + random.random()
            await asyncio.sleep(backoff)
            continue

        if resp.status_code in policy.antibot_statuses:
            if antibot_fail_fast:
                raise AntiBotTriggered(f"anti-bot status={resp.status_code} url={url}")
            backoff = policy.backoff_base * (2 ** (attempt - 1)) + random.random()
            await asyncio.sleep(backoff)
            continue

        if resp.status_code == 200:
            return resp

        # non-200: retry a couple times, then return
        if attempt < policy.max_attempts:
            backoff = 1.0 + random.random()
            await asyncio.sleep(backoff)
            continue
        return resp

    if last_exc is None:
        last_exc_desc = "None"
    else:
        cause = getattr(last_exc, "__cause__", None)
        if cause is not None:
            last_exc_desc = f"{type(last_exc).__name__}({last_exc!r}) cause={type(cause).__name__}({cause!r})"
        else:
            last_exc_desc = f"{type(last_exc).__name__}({last_exc!r})"
    raise RuntimeError(
        f"request failed after retries: {url} attempts={policy.max_attempts} last_exc={last_exc_desc}"
    )


