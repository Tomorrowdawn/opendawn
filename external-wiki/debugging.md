# OpenCode 调试手册

> 记录 OpenCode 启动黑屏/卡死的排查流程和已知问题。

---

## 症状

在特定项目目录下运行 `opencode`，TUI 短暂渲染后黑屏卡死，`timeout` 后进程退出。

## 快速诊断

### 1. 确认是否插件相关

```bash
# 纯模式（跳过所有外部插件）
opencode --pure

# 如果 --pure 正常，问题出在外部插件加载阶段
```

### 2. 查看启动日志

```bash
opencode --print-logs --log-level DEBUG
# 对比 --pure 和非 --pure 的日志差异
```

关键日志标记：
- 正常启动会看到 `service=tui.plugin id=internal:home-footer loading internal tui plugin` 等内部 TUI 插件加载信息
- 如果在内部插件加载之前就卡死 → 某个外部插件编译/加载失败
- `WARN error=Operation timed out after 5000ms worker shutdown failed` → worker 启动过程中崩溃

### 3. 插件加载位置（按顺序）

| 位置 | 类型 | 说明 |
|------|------|------|
| `~/.config/opencode/opencode.json` 的 `plugin` 字段 | 全局 | npm 包或 `file://` 路径 |
| `opencode.json` 的 `plugin` 字段 | 项目 | npm 包或 `file://` 路径 |
| `~/.config/opencode/plugin/` | 全局 | `.ts` / `.js` 文件，自动加载 |
| `.opencode/plugins/` | 项目 | `.ts` / `.js` 文件，自动加载 |

### 4. 定位问题插件

```bash
# 二分法：逐个禁用，找到出问题的那个
mv ~/.config/opencode/plugin ~/.config/opencode/plugin.bak    # 禁用全局插件目录
mv ~/.config/opencode/opencode.json ~/.config/opencode/opencode.json.bak  # 禁用全局配置
mv opencode.json opencode.json.bak                              # 禁用项目配置
```

## 已知问题

### `plugin/` 目录下 TS 文件编译失败导致启动卡死

- **现象**：即使插件代码返回空 hooks（`ENABLED = false`），OpenCode 仍会在启动时编译 `.ts` 文件
- **触发条件**：项目的模块解析环境（如 pnpm monorepo + `pnpm-workspace.yaml`）与插件的 `@opencode-ai/plugin` import 冲突
- **解决**：移除或禁用 `~/.config/opencode/plugin/` 目录下的 TS 文件

### oh-my-openagent 插件已知冲突

- **位置**：`~/.config/opencode/oc.json` → `"plugin": ["oh-my-openagent@latest"]`
- **现象**：该插件在特定项目结构下可能引发兼容性问题
- **解决**：如不使用，移除 `oc.json` 或将文件重命名为 `.bak`

## 配置目录速查

| 路径 | 用途 |
|------|------|
| `~/.opencode/` | OpenCode 安装目录（binary + runtime deps） |
| `~/.config/opencode/opencode.json` | 全局配置文件 |
| `~/.config/opencode/plugin/` | 全局 auto-load 插件 |
| `~/.config/opencode/agent/` | 全局自定义 agent |
| `~/.config/opencode/command/` | 全局自定义命令 |
| `opencode.json` | 项目配置文件 |
| `.opencode/` | 项目级 agent/command/plugin 目录 |
| `~/.cache/opencode/packages/` | npm 插件安装缓存 |
