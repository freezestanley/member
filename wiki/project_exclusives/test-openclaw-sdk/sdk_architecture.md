---
type: concept
created_at: 2026-06-02
last_modified: 2026-06-02
project: test-openclaw-sdk
code_symbols:
  - OpenClaw
  - GatewayClientTransport
  - EventHub
  - normalizeGatewayEvent
  - RpcNamespace
  - useOpenClaw
initial_weight: 1.0
current_weight: 1.0
last_activated: 2026-06-02
access_count: 1
---

# OpenClaw Browser SDK 架构

## 结论

`test-openclaw-sdk` 是 OpenClaw Browser SDK 的集成测试沙盒，`src/sdk/` 即 SDK 本体，通过 Vite alias `@openclaw/browser-sdk` 模拟正式 npm 包使用方式。SDK 采用严格单向分层架构，无外部运行时依赖。

## 分层结构

```
GatewayClientTransport（transport.ts）
  └── EventHub<GatewayEvent>
        ↓ normalizeGatewayEvent（normalize.ts）
  OpenClaw 主类（client.ts）
        └── EventHub<OpenClawEvent>（normalized）
        └── replayByRunId（100 runId × 500 事件缓存）
        └── 9 个 Namespace（agents/sessions/runs/tasks/models/tools/artifacts/approvals/environments）
              ↓
useOpenClaw hook（hooks/useOpenClaw.ts）
              ↓
React UI（App.tsx + components/）
```

依赖方向严格向下，React 层不直接操作 transport 或 EventHub。

## 关键机制

**GatewayClientTransport**：
- WebSocket 帧分两类：`event`（服务端推送）和 `res`（RPC 响应）
- 握手：收到 `connect.challenge` → 发 `sendConnect(hello)` → 收 `hello-ok`
- 所有 pending 请求用 `Map<uuid, Pending>` 管理，按响应 id 路由
- `timeoutMs: null` = 永不超时；`undefined` = 默认 30s
- 断线后指数退避重连：初始 800ms，增长系数 1.7，上限 15s，+300ms 随机抖动

**EventHub<T>**：
- Push-based AsyncIterable，`stream()` 返回多消费者可并发的异步迭代器
- `replayLimit` 控制滑动窗口缓存大小
- `close()` 唤醒所有 waiter，防止 generator 泄漏

**normalizeGatewayEvent**：
- 类型映射：`event.event + payload.stream + payload.phase/status` 三者组合决定 `OpenClawEventType`
- 特殊处理：`sessions.changed` 的 `reason` 字段区分 `session.created/updated/compacted`

**OpenClaw 主类**：
- `startEventPump()`：单一异步循环，消费 transport 原始事件 → normalize → 分发
- `iterateRunEvents(runId)`：replay snapshot + live stream 合并，Set<id> 去重
- **Chat Projection 降级**：Gateway 不发 `assistant.*` 时，`chat.delta` → `assistant.delta`，`chat.final` → `run.completed`，保证消费方 API 兼容

**Namespace 模式**：
- `RpcNamespace` 基类：持有 client + prefix，`call(method)` → `client.request(prefix.method)`
- `AgentsNamespace` 例外：未继承 RpcNamespace，直接调用 `client.request()`（不一致，P1 风险）

## 已知风险

| 优先级 | 问题 | 位置 |
|--------|------|------|
| P0 | 残留 `debugger` 语句，生产会阻断执行 | `sdk/client.ts:67` |
| P1 | `AgentsNamespace` 未继承 `RpcNamespace` | `sdk/client.ts:633` |
| P1 | 无单元测试 | 全 SDK |
| P2 | `EnvironmentsNamespace.create/delete` 运行时抛异常但类型签名无体现 | `sdk/client.ts:843` |

## 边界

- 强依赖浏览器环境（`WebSocket`、`navigator`），不可直接用于 Node.js
- 传输层可替换：`new OpenClaw({ transport: customTransport })` 支持自定义传输

## 相关报告

- 详细分析：`docs/analysis/`（项目内）
- 快速入口：`docs/analysis/index.md`
- 执行流：`docs/analysis/file_map.md`
- 风险清单：`docs/analysis/refactor_roadmap.md`

## 相关概念

[[WebSocket 重连策略]] [[AsyncIterable 事件流]] [[Namespace 模式]]
