# OpenCode 日志与会话定位

> 记录如何定位本地 OpenCode 的运行日志、会话数据和运行时状态。路径中 `~` 代表用户家目录，下面统一用 `~` 脱敏，实际使用时替换为本机路径。

---

## 1. 运行日志（文本日志）

OpenCode 运行时把文本日志写到：

```
~/.local/share/opencode/log/
```

- `opencode.log` — 当前活跃会话日志（追加写入，进程退出后归档）
- `YYYY-MM-DDTHHMMSS.log` — 按会话启动时间归档的历史日志

实时查看：

```bash
tail -f ~/.local/share/opencode/log/opencode.log
```

带级别打印（排查启动问题）：

```bash
opencode --print-logs --log-level DEBUG
```

> 启动卡死/黑屏的完整排查流程见 `external-wiki/debugging.md`。

---

## 2. 会话数据

OpenCode 把所有会话、消息、快照存到一个 **SQLite 数据库**：

```
~/.local/share/opencode/opencode.db
```

伴随文件：

- `opencode.db-shm` — WAL 共享内存
- `opencode.db-wal` — WAL 日志（随写入增长，checkpoint 时合并回主库）

### 2.1 关键表

| 表 | 内容 |
|----|------|
| `project` | 项目注册（`id`、`worktree` 路径、时间戳） |
| `project_directory` | 目录路径 → `project_id` 的映射（一个项目可关联多个目录） |
| `session` | 会话元数据：`id`、`project_id`、`title`、`directory`、时间戳、`cost`、`tokens_*` |
| `message` / `part` | 消息与消息分片（实际对话内容） |
| `session_message` | 会话与消息的关联 |
| `session_context_epoch` | 会话上下文压缩纪元 |
| `todo` | 会话级 TODO |

### 2.2 找到某项目的所有会话

```bash
# 列出项目及其最新更新时间
sqlite3 ~/.local/share/opencode/opencode.db \
  "SELECT id, worktree, datetime(time_updated/1000,'unixepoch','localtime')
   FROM project ORDER BY time_updated DESC;"

# 按目录路径模糊匹配，列出该项目的会话（最新在上）
sqlite3 ~/.local/share/opencode/opencode.db \
  "SELECT s.id, datetime(s.time_updated/1000,'unixepoch','localtime') AS updated, s.title
   FROM session s
   JOIN project_directory pd ON pd.project_id = s.project_id
   WHERE pd.directory LIKE '%/yuubot%'
   ORDER BY s.time_updated DESC
   LIMIT 20;"
```

### 2.3 旧版 JSON 存储（已废弃，仅历史遗留）

```
~/.local/share/opencode/storage/
├── session/<project_id_or_global>/ses_*.json   # 旧会话元数据
├── message/                                    # 旧消息
├── part/                                       # 旧消息分片
├── project/<sha1>.json                         # 旧项目映射
├── snapshot/<sha1>/                            # 文件快照（git 仓库格式）
└── ...
```

> 新版本数据已全部迁到 SQLite；上述 JSON 目录只在老安装里还有残留。判定项目 ID 的方式在旧版是 `sha1(绝对路径)`，在新版用 `project` 表的 `id` 字段（与路径无直接哈希关系，需查表）。

---

## 3. 运行时状态

opencode 把可变运行的轻状态放在 XDG state 目录：

```
~/.local/state/opencode/
```

| 文件 | 用途 |
|------|------|
| `frecency.jsonl` | 文件访问最近度（文件选取排序） |
| `prompt-history.jsonl` | 提示词历史 |
| `model.json` | 当前模型选择缓存 |
| `kv.json` | 杂项键值缓存 |
| `locks/` | 进程文件锁 |

---

## 4. 速查清单

| 想看什么 | 去哪找 |
|----------|--------|
| 本次运行文本日志 | `~/.local/share/opencode/log/opencode.log` |
| 历史会话元数据/内容 | `sqlite3 ~/.local/share/opencode/opencode.db` |
| 某项目的所有会话 | `session` 表 JOIN `project_directory`（见 2.2） |
| 当前模型/cedlocale 等缓存 | `~/.local/state/opencode/` |
| 文件快照/回滚 | `~/.local/share/opencode/snapshot/` 或 SQLite |

---

## 5. 配置目录速查（与日志区分）

配置目录与日志/状态不同，列在此便于区分：

| 路径 | 用途 |
|------|------|
| `~/.config/opencode/opencode.json` | 全局配置 |
| `~/.config/opencode/tui.json` | 全局 TUI 配置 |
| `~/.config/opencode/agent(s)/` | 全局自定义 agent |
| `~/.config/opencode/command(s)/` | 全局自定义命令 |
| `~/.config/opencode/plugin(s)/` | 全局 auto-load 插件 |
| `<project>/opencode.json` | 项目配置 |
| `<project>/.opencode/` | 项目级 agent/command/plugin/skill 目录 |
