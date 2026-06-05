---
title: "Strategy Pattern: Replace Conditionals with Composition"
category: case-study
tags:
  - strategy
  - composition
  - conditional
  - branching
  - polymorphism
related:
  - ../best-practice/composition-over-inheritance.md
summary: "Replacing sprawling if/elif/else conditional branches with composable strategy objects — algorithms vary independently and are testable in isolation."
---

# Strategy Pattern: Replace Conditionals with Composition

## 场景

支付系统需要支持微信支付、支付宝、银行卡三种支付方式，且未来可能接入 Apple Pay、PayPal 等新渠道。支付方式在运行时根据用户选择动态决定——配置下发、前端传参、或 A/B 实验切换。

## 坏代码

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class PaymentOrder:
    order_id: str
    amount: Decimal
    payment_type: str  # "wechat" | "alipay" | "bank"


async def charge(order: PaymentOrder, user_ctx: dict[str, Any]) -> bool:
    if order.payment_type == "wechat":
        # 签名、调用微信 SDK、处理回调
        resp = await wechat_sdk.pay(
            appid=config.WECHAT_APPID,
            mch_id=config.WECHAT_MCHID,
            amount=str(order.amount),
            notify_url="https://api.example.com/callback/wechat",
        )
        return resp["return_code"] == "SUCCESS"
    elif order.payment_type == "alipay":
        resp = await alipay_sdk.create_order(
            out_trade_no=order.order_id,
            total_amount=float(order.amount),
            subject="订单支付",
        )
        return resp.is_success()
    elif order.payment_type == "bank":
        resp = await bank_gateway.charge(
            card_no=user_ctx["card_no"],
            amount=order.amount,
            cvv=user_ctx["cvv"],
        )
        return resp.status == "settled"
    else:
        raise ValueError(f"Unknown payment type: {order.payment_type}")
```

## 为什么坏

1. **违反开闭原则**：每增加一种支付方式，都必须侵入 `charge` 函数添加新的 `elif` 分支——修改已有代码而非扩展。
2. **分支蔓延**：退款（`refund`）、查询（`query`）、回调处理（`handle_callback`）等函数各自复制同样的 `if-elif` 链。修改一个分支的逻辑需要同步 N 处。
3. **隐式耦合**：`user_ctx["card_no"]` 这种上下文字典的键名是隐式契约，银行支付特有的字段泄漏到了通用函数签名中。
4. **测试膨胀**：测试 `charge` 需要 mock 所有支付渠道的 SDK，即使你只关注微信支付的逻辑。

## 好代码

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class ChargeRequest:
    order_id: str
    amount: Decimal


@dataclass(frozen=True)
class ChargeResult:
    success: bool
    transaction_id: str


class PaymentStrategy(Protocol):
    """支付策略协议——所有支付渠道的统一接口。"""

    async def charge(self, request: ChargeRequest) -> ChargeResult: ...
    async def refund(self, transaction_id: str, amount: Decimal) -> ChargeResult: ...


class WechatPayment:
    def __init__(self, appid: str, mch_id: str, notify_url: str) -> None:
        self._appid = appid
        self._mch_id = mch_id
        self._notify_url = notify_url

    async def charge(self, request: ChargeRequest) -> ChargeResult:
        resp = await wechat_sdk.pay(
            appid=self._appid, mch_id=self._mch_id,
            amount=str(request.amount), notify_url=self._notify_url,
        )
        return ChargeResult(
            success=resp["return_code"] == "SUCCESS",
            transaction_id=resp["transaction_id"],
        )

    async def refund(self, transaction_id: str, amount: Decimal) -> ChargeResult:
        ...


class AlipayPayment:
    def __init__(self, app_id: str, private_key: str) -> None:
        self._app_id = app_id
        self._private_key = private_key

    async def charge(self, request: ChargeRequest) -> ChargeResult:
        resp = await alipay_sdk.create_order(
            out_trade_no=request.order_id, total_amount=float(request.amount),
        )
        return ChargeResult(
            success=resp.is_success(), transaction_id=resp.trade_no,
        )

    async def refund(self, transaction_id: str, amount: Decimal) -> ChargeResult:
        ...


def get_payment_strategy(payment_type: str, /, **config: str) -> PaymentStrategy:
    """工厂方法——根据类型返回对应的策略实例。"""
    strategies: dict[str, type[PaymentStrategy]] = {
        "wechat": WechatPayment,
        "alipay": AlipayPayment,
        "bank": BankPayment,
    }
    cls = strategies.get(payment_type)
    if cls is None:
        raise ValueError(f"Unknown payment type: {payment_type}")
    return cls(**config)  # 各策略按需提取自己需要的配置字段


# 调用端——不再需要知道具体是哪种支付方式
async def process_payment(strategy: PaymentStrategy, request: ChargeRequest) -> ChargeResult:
    """业务层只依赖 Protocol，不依赖具体实现。"""
    return await strategy.charge(request)
```

## 为什么好 / 关键差异

1. **开闭原则**：新增支付渠道只需创建一个新类实现 `PaymentStrategy` 协议并注册到工厂——零修改现有代码。
2. **消除分支重复**：`charge`/`refund`/`query` 无需各自维护 `if-elif` 链，每个策略类内部自治，编译期即可通过类型检查发现契约违约。
3. **依赖倒置**：业务层（`process_payment`）只依赖 `PaymentStrategy` 抽象协议，不依赖 `WechatPayment` / `AlipayPayment` 具体实现。测试时传 `MockPayment` 即可。
4. **配置封装**：微信的 `appid`/`mch_id` 和支付宝的 `private_key` 各自封装在构造器中，不会像 `user_ctx["card_no"]` 那样泄漏到通用上下文。
