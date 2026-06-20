---
title: "CRUD Recipe: FastAPI Application"
category: cookbook
tags:
  - crud
  - fastapi
  - repository
  - serde
  - serialization
  - schema
  - api
  - endpoint
  - sqlalchemy
  - msgspec
  - dependency-injection
related:
  - ../best-practice/serde-boundary.md
  - ../best-practice/type-safety.md
  - ../best-practice/composition-over-inheritance.md
  - ../case-study/repository-pattern.md
  - ../case-study/serde-schema.md
  - ../case-study/dependency-injection.md
  - ../case-study/factory-pattern.md
summary: "Complete FastAPI CRUD application template. Domain schemas, repository Protocol, service layer, API endpoints with schema conversion. Copy, adapt 🔌 extension points, done."
---

# CRUD Recipe: FastAPI Application

> **This is a template, not a tutorial.** It exists so you can copy the structure, adapt the `🔌` markers to your domain, and ship. Read the code, not the prose. The prose only explains _where_ to adapt.

---

## Project Structure

```
src/
  app/
    domain/
      models.py         # Domain schemas (msgspec.Struct)
    api/
      schemas.py        # Request/Response DTOs — the serde boundary
      router.py         # FastAPI route handlers
      deps.py           # Dependency injection wiring
    service/
      task_service.py   # Business logic
    repository/
      protocol.py       # Repository Protocol (interface)
      sql.py            # SQLAlchemy async implementation
    main.py             # App factory (composition root)
  pyproject.toml
```

Every layer has exactly one job. If you can't describe a file's job in 5 words, the layer is entangled.

---

## 1. Domain Models

`src/app/domain/models.py` — the core entity. Pure data, no ORM, no HTTP. Uses `msgspec.Struct` for zero-cost serialization and immutability.

```python
from __future__ import annotations

import enum
import msgspec
import uuid


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Task(msgspec.Struct, frozen=True):
    """Domain entity — not coupled to any storage or transport layer."""
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    created_at: str = ""  # ISO 8601

# 🔌 EXTENSION: add another entity (e.g. Project, Comment) as a new Struct here.
#    Keep it frozen=True. Never put ORM or HTTP concerns in domain models.
```

The domain model is the truth. Nothing outside this file knows how a `Task` is stored or serialized.

---

## 2. API Schemas — The Serde Boundary

`src/app/api/schemas.py` — **This is the most important file.** It defines what enters and leaves your HTTP API. These are _separate_ from domain models so the API contract can evolve independently of the domain.

```python
from __future__ import annotations

import msgspec

from app.domain.models import Task, TaskStatus


# ── Request schemas (untrusted data from clients) ──────────────────────────

class TaskCreateRequest(msgspec.Struct):
    """What the client sends to create a task."""
    title: str
    description: str = ""


class TaskUpdateRequest(msgspec.Struct, frozen=True):
    """Partial update — all fields optional so client sends only what changed."""
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None


# ── Response schemas (what the client receives) ────────────────────────────

class TaskResponse(msgspec.Struct):
    """Public representation of a task. May differ from domain model."""
    id: str
    title: str
    description: str
    status: str        # serialized as string, not enum
    created_at: str


class TaskListResponse(msgspec.Struct):
    items: list[TaskResponse]
    total: int


# ──🔌 EXTENSION: Schema Conversion — the core pattern ──────────────────────
#
#   For every entity, write TWO conversion functions:
#     1. request → domain   (validate at boundary, convert to internal type)
#     2. domain → response  (convert internal type to public shape)
#
#   These functions are the ONLY place where request/domain/response shapes
#   are mapped. When the API contract changes, ONLY this file changes.

def task_create_to_domain(req: TaskCreateRequest) -> Task:
    """Convert validated request → domain entity (new task, no id yet)."""
    import uuid
    from datetime import datetime, timezone

    return Task(
        id=str(uuid.uuid4()),
        title=req.title,
        description=req.description,
        status=TaskStatus.TODO,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def task_update_to_domain(existing: Task, req: TaskUpdateRequest) -> Task:
    """Merge partial update request into existing domain entity."""
    return Task(
        id=existing.id,
        title=req.title if req.title is not None else existing.title,
        description=req.description if req.description is not None else existing.description,
        status=req.status if req.status is not None else existing.status,
        created_at=existing.created_at,
    )


def task_to_response(task: Task) -> TaskResponse:
    """Convert domain entity → public response DTO."""
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        status=task.status.value,
        created_at=task.created_at,
    )


# 🔌 EXTENSION: For a new entity (e.g. Project), replicate the pattern:
#    1. ProjectCreateRequest, ProjectUpdateRequest, ProjectResponse
#    2. project_create_to_domain(), project_update_to_domain(), project_to_response()
```

**The rule**: request/response schemas never leak into service or repository layers. Domain models never leak into HTTP handlers. The conversion functions are the sole bridge.

---

## 3. Repository Layer

### 3a. Protocol (Interface)

`src/app/repository/protocol.py` — defines _what_ data operations exist, not _how_. Every storage backend implements this.

```python
from __future__ import annotations

from typing import Protocol

from app.domain.models import Task


class TaskRepository(Protocol):
    """Data access contract — business logic depends on this, never on SQL."""

    async def get_by_id(self, task_id: str) -> Task | None: ...
    async def list_all(self, *, offset: int = 0, limit: int = 20) -> list[Task]: ...
    async def count(self) -> int: ...
    async def insert(self, task: Task) -> Task: ...
    async def update(self, task: Task) -> Task: ...
    async def delete(self, task_id: str) -> bool: ...


# 🔌 EXTENSION: For a new entity, add a new Protocol here.
#    e.g. ProjectRepository with get_by_id, list_all, insert, update, delete.
```

### 3b. SQLAlchemy Implementation

`src/app/repository/sql.py` — the concrete implementation. All SQL lives here and nowhere else.

```python
from __future__ import annotations

from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Task
from app.repository.protocol import TaskRepository
from attrs import define


@define
class SqlTaskRepository:
    """SQLAlchemy async implementation of TaskRepository."""
    session: AsyncSession

    async def get_by_id(self, task_id: str) -> Task | None:
        result = await self.session.execute(
            select(Task).where(Task.id == task_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, *, offset: int = 0, limit: int = 20) -> list[Task]:
        result = await self.session.execute(
            select(Task).offset(offset).limit(limit).order_by(Task.created_at.desc())
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(select(func.count(Task.id)))
        return result.scalar_one()

    async def insert(self, task: Task) -> Task:
        self.session.add(task)
        await self.session.flush()
        return task

    async def update(self, task: Task) -> Task:
        await self.session.merge(task)
        await self.session.flush()
        return task

    async def delete(self, task_id: str) -> bool:
        result = await self.session.execute(
            sa_delete(Task).where(Task.id == task_id)
        )
        await self.session.flush()
        return result.rowcount > 0


# 🔌 EXTENSION: For a new entity, replicate SqlTaskRepository pattern.
#    All SQL goes here. Service layer never touches Session or queries.
```

---

## 4. Service Layer

`src/app/service/task_service.py` — business logic. Pure orchestration: receives domain objects, delegates to repository, returns domain objects. Zero HTTP, zero SQL.

```python
from __future__ import annotations

from app.domain.models import Task
from app.repository.protocol import TaskRepository
from attrs import define


@define
class TaskService:
    """Business logic for tasks. Depends on TaskRepository Protocol, not SQL."""
    repo: TaskRepository

    async def create(self, task: Task) -> Task:
        return await self.repo.insert(task)

    async def get(self, task_id: str) -> Task | None:
        return await self.repo.get_by_id(task_id)

    async def list_all(self, *, offset: int = 0, limit: int = 20) -> tuple[list[Task], int]:
        tasks = await self.repo.list_all(offset=offset, limit=limit)
        total = await self.repo.count()
        return tasks, total

    async def update(self, task: Task) -> Task | None:
        existing = await self.repo.get_by_id(task.id)
        if existing is None:
            return None
        return await self.repo.update(task)

    async def delete(self, task_id: str) -> bool:
        return await self.repo.delete(task_id)


# 🔌 EXTENSION: For a new entity, replicate TaskService.
#    Add cross-entity logic here (e.g. "closing a project archives all its tasks").
```

---

## 5. Dependency Injection

`src/app/api/deps.py` — the wiring. FastAPI's `Depends()` calls these to construct dependencies.

```python
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.repository.protocol import TaskRepository
from app.repository.sql import SqlTaskRepository
from app.service.task_service import TaskService


# ── Database engine (created once per app instance) ────────────────────────

def create_engine(database_url: str):
    return create_async_engine(database_url, echo=False)


def create_session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── FastAPI dependency callables ───────────────────────────────────────────

async def get_db_session(
    request: Request,  # FastAPI Request
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session per request. Closed after response."""
    session_factory: async_sessionmaker = request.app.state.session_factory
    async with session_factory() as session:
        yield session


async def get_task_repository(
    session: AsyncSession = Depends(get_db_session),
) -> TaskRepository:
    return SqlTaskRepository(session)


async def get_task_service(
    repo: TaskRepository = Depends(get_task_repository),
) -> TaskService:
    return TaskService(repo)


# 🔌 EXTENSION: For a new entity, add get_x_repository() and get_x_service().
#    Each depends on the one before. Chain: session → repo → service.
```

---

## 6. API Router

`src/app/api/router.py` — HTTP handlers. Thin: parse request → call service → format response. No business logic, no SQL.

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.schemas import (
    TaskCreateRequest,
    TaskUpdateRequest,
    TaskResponse,
    TaskListResponse,
    task_create_to_domain,
    task_update_to_domain,
    task_to_response,
)
from app.api.deps import get_task_service
from app.service.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreateRequest,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Create a new task."""
    domain_task = task_create_to_domain(body)  # ← serde boundary
    created = await service.create(domain_task)
    return task_to_response(created)           # ← serde boundary


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Get a task by ID."""
    task = await service.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_to_response(task)


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    service: TaskService = Depends(get_task_service),
) -> TaskListResponse:
    """List tasks with pagination."""
    tasks, total = await service.list_all(offset=offset, limit=limit)
    return TaskListResponse(
        items=[task_to_response(t) for t in tasks],
        total=total,
    )


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    body: TaskUpdateRequest,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    """Partial update a task."""
    existing = await service.get(task_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Task not found")

    domain_task = task_update_to_domain(existing, body)  # ← merge at boundary
    updated = await service.update(domain_task)
    if updated is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_to_response(updated)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> None:
    """Delete a task."""
    deleted = await service.delete(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")


# 🔌 EXTENSION: For a new entity, replicate the router pattern.
#    New APIRouter(prefix="/projects"), same structure: body → to_domain → service → to_response.
```

**The router's only job**: convert HTTP → domain at entry, domain → HTTP at exit. Every endpoint follows the same 3-step shape:
1. Convert request to domain (`x_to_domain()`)
2. Delegate to service
3. Convert domain to response (`x_to_response()`)

---

## 7. App Factory

`src/app/main.py` — the composition root. Creates and wires everything. Called once at startup.

```python
from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.router import router as task_router
from app.api.deps import create_engine, create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle."""
    # Startup
    engine = create_engine(app.state.database_url)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    yield
    # Shutdown
    await engine.dispose()


def create_app(database_url: str) -> FastAPI:
    """App factory — the single place where everything is wired together."""
    app = FastAPI(title="Task API", lifespan=lifespan)
    app.state.database_url = database_url
    app.include_router(task_router)
    return app


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    import os

    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///tasks.db")
    app = create_app(db_url)
    uvicorn.run(app, host="0.0.0.0", port=8000)


# 🔌 EXTENSION: When adding a new entity router, include it here:
#    app.include_router(project_router)
```

---

## 8. Extension Guide: Adding a New Entity

When adding a new entity (e.g. `Project`), follow this table. Each row is one file to touch:

| Step | File | What to do |
|------|------|-------------|
| 1 | `domain/models.py` | Add `Project(msgspec.Struct, frozen=True)` |
| 2 | `api/schemas.py` | Add `ProjectCreateRequest`, `ProjectUpdateRequest`, `ProjectResponse` + 3 conversion functions |
| 3 | `repository/protocol.py` | Add `ProjectRepository(Protocol)` |
| 4 | `repository/sql.py` | Add `SqlProjectRepository` |
| 5 | `service/project_service.py` | Add `ProjectService` (new file, same shape as `TaskService`) |
| 6 | `api/deps.py` | Add `get_project_repository()` + `get_project_service()` |
| 7 | `api/router.py` or `api/project_router.py` | Add `APIRouter(prefix="/projects")` with CRUD endpoints |
| 8 | `main.py` | `app.include_router(project_router)` |

**The 3 conversion functions are the only creative work.** Everything else is mechanical. Spend your brain cycles on the schema design — what shape does the client need vs. what shape does the domain need?

---

## Summary: The Data Flow

```
HTTP Request (JSON bytes)
    │
    ▼  [FastAPI parses → TaskCreateRequest]
    │
    ├─ task_create_to_domain()   ← 🔌 SCHEMA CONVERSION (serde boundary)
    │
    ▼  [Task domain entity]
    │
    ├─ TaskService.create()
    │     └─ TaskRepository.insert() → SQL
    │
    ▼  [Task domain entity (with id)]
    │
    ├─ task_to_response()        ← 🔌 SCHEMA CONVERSION (serde boundary)
    │
    ▼
HTTP Response (TaskResponse → JSON)
```

Every `🔌` in this flow is a point where the shape of data changes. These conversion functions are the extension points — when the API evolves, they are the only things that change.

---

## Related Docs

- `best-practice/serde-boundary.md` — why schemas at boundaries matter
- `best-practice/type-safety.md` — ban `Any`, use precise types
- `case-study/repository-pattern.md` — Protocol + implementation decoupling
- `case-study/serde-schema.md` — msgspec.Struct validation at the edge
- `case-study/dependency-injection.md` — constructor injection over globals
- `case-study/factory-pattern.md` — `@classmethod` factories for multi-source creation
