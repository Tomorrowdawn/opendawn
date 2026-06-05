---
title: "Exception Swallowing: The Silent Bug Factory"
category: case-study
tags:
  - exception
  - error-handling
  - except-pass
  - debugging
related:
  - ../best-practice/fail-fast.md
summary: "except: pass and overly broad except Exception are the most insidious bug factories — errors vanish without a trace, corrupting state silently."
---

# Exception Swallowing: The Silent Bug Factory

## 场景

你有一个 `PaymentService`，调用第三方支付网关的 API。网络抖动、超时、凭证过期、返回格式变化……各种失败都可能发生。

## 坏代码

```python
class PaymentService:
    async def process_payment(self, order_id: str, amount: int) -> dict | None:
        """返回支付结果，失败时返回 None"""
        try:
            resp = await self._gateway.charge(order_id, amount)
            return resp.json()
        except Exception:
            return None

    async def refund_payment(self, payment_id: str) -> bool:
        """退款，成功返回 True"""
        try:
            await self._gateway.refund(payment_id)
            return True
        except:
            pass  # 吞掉一切
        return False

    async def batch_process(self, orders: list[tuple[str, int]]) -> list[dict]:
        results = []
        for order_id, amount in orders:
            result = await self.process_payment(order_id, amount)
            if result is not None:
                results.append(result)
            # 失败的订单静默跳过
        return results
```

## 为什么坏

1. **信息黑洞**：`except Exception: return None` 吞掉了所有异常信息 —— 是网络超时？是凭证过期（401）？是 JSON 解析失败？还是代码自身的 `AttributeError` bug？全部变成了一个沉默的 `None`。
2. **裸 `except:` 更危险**：`except:` 不加异常类型，连 `KeyboardInterrupt`、`SystemExit`、`GeneratorExit` 都吞掉。用户 Ctrl+C 终止程序 → 被当成"支付失败"静默处理。
3. **根因追查不可能**：生产环境中 `batch_process` 返回了空列表，你不知道是 10 个订单都网络超时还是 1 个 JSON bug 导致所有后续都跳过。日志里没有任何线索。
4. **自欺欺人的错误处理**：`return None` 或 `return False` 并非真正"处理"了错误——它只是把错误推迟到下游。下游收到 `None` 时，同样困惑：这个 `None` 是正常的空结果，还是上游崩溃了？
5. **隐藏真实 bug**：如果 `_gateway.charge(order_id, amount)` 因为传参错误抛出 `TypeError`，它也会被 `except Exception` 吞掉。本该立即修复的代码缺陷，变成了"偶尔支付失败"的幽灵问题。

## 好代码

```python
import logging
from typing import NoReturn

logger = logging.getLogger(__name__)

class PaymentError(Exception):
    """业务层支付异常"""
    def __init__(self, message: str, original: Exception | None = None):
        super().__init__(message)
        self.original = original

class PaymentService:
    async def process_payment(self, order_id: str, amount: int) -> dict:
        try:
            resp = await self._gateway.charge(order_id, amount)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException as e:
            logger.error("支付网关超时 order=%s amount=%s", order_id, amount)
            raise PaymentError(f"支付超时: {order_id}", original=e) from e
        except httpx.HTTPStatusError as e:
            logger.error(
                "支付网关返回错误 order=%s status=%s body=%s",
                order_id, e.response.status_code, e.response.text,
            )
            raise PaymentError(
                f"支付网关错误({e.response.status_code}): {order_id}", original=e
            ) from e
        except json.JSONDecodeError as e:
            logger.error("支付响应 JSON 解析失败 order=%s", order_id)
            raise PaymentError(f"支付响应格式异常: {order_id}", original=e) from e

    async def batch_process(self, orders: list[tuple[str, int]]) -> dict[str, dict]:
        results: dict[str, dict] = {}
        failed: dict[str, str] = {}
        for order_id, amount in orders:
            try:
                results[order_id] = await self.process_payment(order_id, amount)
            except PaymentError as e:
                logger.warning("订单 %s 处理失败: %s", order_id, e)
                failed[order_id] = str(e)
        return {"success": results, "failed": failed}
```

## 为什么好 / 关键差异

- **捕获具体异常类型**：`httpx.TimeoutException`、`httpx.HTTPStatusError`、`json.JSONDecodeError` —— 每种失败有独立的处理逻辑，日志包含足够上下文。
- **记录 + 重新抛出**：日志记录了 `order_id`、`amount`、状态码、响应体等关键信息后，将原始异常包装为业务层 `PaymentError` 重新抛出。上层可以决定是重试、告警还是降级。
- **`from e` 保留异常链**：`raise PaymentError(...) from e` 保留原始异常作为 `__cause__`，堆栈追踪完整，不会丢失任何调试信息。
- **绝不吞异常**：如果发生意料之外的异常（如 `AttributeError`），它会直接传播到顶层，被全局异常处理器捕获并报警。真正的 bug 不会被隐藏。
- **批量操作分层处理**：`batch_process` 捕获 `PaymentError`（可预期的业务异常），记录失败但继续处理其他订单。未预期的异常不捕获，任其传播。

> 核心原则：只捕获你知道如何恢复的异常。记录上下文后重新抛出（或包装为业务异常）。永远不要 `except: pass`。
