---
title: "Facade Pattern: Clean Boundaries for Complex Subsystems"
category: case-study
tags:
  - facade
  - subsystem
  - abstraction
  - boundary
  - api-design
related:
  - ../best-practice/composition-over-inheritance.md
summary: "Clean subsystem entry point that hides internal complexity without leaking implementation details — a disciplined architectural boundary."
---

# Facade Pattern: Clean Boundaries for Complex Subsystems

## 场景

对接第三方支付 SDK（如 Ping++ 或 Stripe），涉及 6 个底层 API：签名生成、请求加密、HTTP 发送、回调签名验证、响应解密、重试逻辑。业务代码——下单、退款、查询——需要依次调用这些 API，加上错误处理和日志。

## 坏代码

```python
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from third_party.payment_sdk import PaymentClient, CryptoEngine, RetryPolicy

logger = logging.getLogger(__name__)
client = PaymentClient(api_key="sk_live_xxx", base_url="https://pay.example.com")
crypto = CryptoEngine(master_key=b"secret_master_key")
retry = RetryPolicy(max_attempts=3, backoff_base=2.0)


async def create_order(amount: int, currency: str, description: str) -> dict[str, Any]:
    """每个业务函数都要重复 6 步底层操作。"""
    payload = {
        "amount": amount, "currency": currency,
        "description": description, "timestamp": int(time()),
    }

    # 步骤 1：签名
    payload_str = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        b"app_secret", payload_str.encode(), hashlib.sha256,
    ).hexdigest()

    # 步骤 2：加密
    encrypted = crypto.encrypt(payload_str.encode())

    # 步骤 3：发送（带重试）
    for attempt in range(3):
        try:
            resp = await client.post("/v1/charges", body=encrypted, signature=signature)
            break
        except Exception:
            if attempt == 2:
                raise
            await sleep(2.0 ** attempt)

    # 步骤 4：解密
    decrypted = crypto.decrypt(resp.body)

    # 步骤 5：验证响应签名
    if resp.signature != hmac.new(b"app_secret", decrypted, hashlib.sha256).hexdigest():
        raise ValueError("Response signature mismatch")

    return json.loads(decrypted)


async def refund_order(charge_id: str, amount: int) -> dict[str, Any]:
    """同样的 6 步重复——签名、加密、发送、重试、解密、验证。"""
    payload = {"charge_id": charge_id, "amount": amount, "timestamp": int(time())}

    payload_str = json.dumps(payload, sort_keys=True)
    signature = hmac.new(b"app_secret", payload_str.encode(), hashlib.sha256).hexdigest()
    encrypted = crypto.encrypt(payload_str.encode())

    for attempt in range(3):
        try:
            resp = await client.post(f"/v1/charges/{charge_id}/refund", body=encrypted, signature=signature)
            break
        except Exception:
            if attempt == 2:
                raise
            await sleep(2.0 ** attempt)

    decrypted = crypto.decrypt(resp.body)
    if resp.signature != hmac.new(b"app_secret", decrypted, hashlib.sha256).hexdigest():
        raise ValueError("Response signature mismatch")

    return json.loads(decrypted)
```

## 为什么坏

1. **签名逻辑散布**：`hmac.new(b"app_secret", payload_str.encode(), hashlib.sha256)` 出现在每一个业务函数中——秘钥泄露风险高（一处拼错就会暴露），修改签名算法需要全局搜索替换。
2. **6 步底层操作充斥业务函数**：业务开发者需要理解加密引擎、重试策略、签名验证才能写"退款"——认知负荷过高。
3. **错误处理重复**：重试逻辑、签名验证失败、解密错误等分散在各处，无法统一调整重试策略或错误格式。
4. **无法独立测试业务逻辑**：测试 `create_order` 时必须 mock `PaymentClient` + `CryptoEngine` + `RetryPolicy` 三个底层模块。

## 好代码

```python
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from asyncio import sleep
from dataclasses import dataclass
from time import time
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChargeRequest:
    amount: int
    currency: str
    description: str


@dataclass(frozen=True)
class ChargeResult:
    charge_id: str
    status: str
    amount: int


class PaymentFacade:
    """统一外观——封装签名、加密、重试、解密、验证，对外只暴露业务接口。"""

    def __init__(
        self,
        *,
        api_key: str,
        app_secret: bytes,
        master_key: bytes,
        base_url: str = "https://pay.example.com",
        max_retries: int = 3,
    ) -> None:
        self._client = PaymentClient(api_key=api_key, base_url=base_url)
        self._crypto = CryptoEngine(master_key=master_key)
        self._app_secret = app_secret
        self._max_retries = max_retries

    async def charge(self, request: ChargeRequest) -> ChargeResult:
        data = await self._send("/v1/charges", {
            "amount": request.amount,
            "currency": request.currency,
            "description": request.description,
        })
        return ChargeResult(
            charge_id=data["id"], status=data["status"], amount=data["amount"],
        )

    async def refund(self, charge_id: str, amount: int) -> dict[str, Any]:
        return await self._send(f"/v1/charges/{charge_id}/refund", {
            "charge_id": charge_id,
            "amount": amount,
        })

    # --- 内部：一次性实现 6 步底层操作 ---

    def _sign(self, payload: str) -> str:
        return hmac.new(self._app_secret, payload.encode(), hashlib.sha256).hexdigest()

    def _verify_signature(self, payload: bytes, signature: str) -> None:
        expected = hmac.new(self._app_secret, payload, hashlib.sha256).hexdigest()
        if signature != expected:
            raise ValueError("Response signature mismatch")

    async def _send(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload["timestamp"] = int(time())
        payload_str = json.dumps(payload, sort_keys=True)

        signature = self._sign(payload_str)
        encrypted = self._crypto.encrypt(payload_str.encode())

        for attempt in range(self._max_retries):
            try:
                resp = await self._client.post(path, body=encrypted, signature=signature)
                break
            except Exception:
                if attempt == self._max_retries - 1:
                    raise
                await sleep(2.0 ** attempt)

        decrypted = self._crypto.decrypt(resp.body)
        self._verify_signature(decrypted, resp.signature)
        return json.loads(decrypted)


# --- 业务代码——简洁如声明 ---
facade = PaymentFacade(api_key="sk_live_xxx", app_secret=b"app_secret", master_key=b"secret_key")

result = await facade.charge(ChargeRequest(amount=100, currency="CNY", description="年费会员"))
```

## 为什么好 / 关键差异

1. **单一入口**：签名算法只出现在 `_sign` / `_verify_signature` 两个私有方法中——修改签名算法、替换加密库、升级重试策略，改一处全局生效。
2. **业务接口即文档**：`charge(ChargeRequest) -> ChargeResult` 一眼看懂业务意图，无需穿透 6 步底层操作。
3. **秘钥集中管理**：`app_secret` / `master_key` 仅存在于 `PaymentFacade` 构造时，不会在 10 个业务函数中四处散落——降低泄露风险。
4. **可替换性**：需要从 Ping++ 迁移到 Stripe 时，只需新建 `StripePaymentFacade` 实现相同接口，业务代码零修改。
