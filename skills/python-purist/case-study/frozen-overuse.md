---
title: "Frozen Overuse: Conceptual Freeze vs Runtime Freeze"
category: case-study
tags:
  - frozen
  - mutability
  - msgspec
  - attrs
  - tuple
  - list
  - append-only
  - class-design
  - anti-pattern
related:
  - ../best-practice/struct-vs-define.md
  - ../best-practice/type-safety.md
summary: "AI agents often turn conceptual constraints into `frozen=True`, then convert lists to tuples and make normal updates painful. Freeze only for real runtime immutability: hash keys, shared messages, config, or race prevention."
---

# Frozen Overuse: Conceptual Freeze vs Runtime Freeze

## Scenario

A conversation history is append-only: callers may append a new message, but they must never edit or reorder earlier messages. An agent interprets "append-only" as "make the whole struct frozen", converts the list to a tuple, and forces every update to rebuild the object.

## Bad Code: Frozen Struct With Tuple Cargo Culting

```python
import msgspec


class Message(msgspec.Struct, frozen=True):
    id: str
    text: str


class Conversation(msgspec.Struct, frozen=True):
    id: str
    messages: tuple[Message, ...]


def append_message(conversation: Conversation, message: Message) -> Conversation:
    return Conversation(
        id=conversation.id,
        messages=(*conversation.messages, message),
    )
```

## Why It's Bad

1. **It confuses two meanings of "frozen"**: the domain rule is "do not mutate historical entries"; the implementation says "the container itself can never be updated." Those are different contracts.

2. **Every normal update becomes object reconstruction**: appending one message now requires building a new tuple and a new conversation. That cost and ceremony spreads through callers.

3. **It pushes accidental complexity into persistence and event flow**: code that already owns the conversation must now decide whether to replace references, write the whole aggregate, or thread the new object through every layer.

4. **Tuple does not express append-only intent**: a tuple says fixed-size sequence. It does not say "history entries cannot be edited." Tests and APIs express that rule more directly.

## Good Code: Mutable Container With Append-Only API

```python
import msgspec


class Message(msgspec.Struct, frozen=True):
    id: str
    text: str


class Conversation(msgspec.Struct):
    id: str
    messages: list[Message]


def append_message(conversation: Conversation, message: Message) -> None:
    conversation.messages.append(message)
```

The aggregate is mutable because the business process mutates it. Individual messages may still be frozen because a sent message is a completed value: changing it after publication would be a different event.

## Good Code: Real Runtime Freeze

```python
import msgspec


class MessagePublished(msgspec.Struct, frozen=True):
    conversation_id: str
    message_id: str
    created_at: str
```

This event is frozen because it is published to other components. After publication, no producer or consumer should be able to rewrite it through a shared reference.

## Decision Rule

Use `frozen=True` only when mutation would break a concrete runtime contract:

- The object is a dict key, set member, or cache key.
- The object is a loaded config that must stay stable for the process lifetime.
- The object is a published event/message/snapshot read by multiple consumers.
- The object crosses concurrency or distribution boundaries where shared mutation creates races.

Do not use `frozen=True` merely to document "please don't edit this." For append-only data, model the allowed operation directly: expose append, forbid replace/delete through API boundaries, and test that historical entries are preserved.
