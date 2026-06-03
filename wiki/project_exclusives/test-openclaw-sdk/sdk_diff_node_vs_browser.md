---
type: concept
created_at: 2026-06-02
last_modified: 2026-06-03
project: test-openclaw-sdk
code_symbols:
  - GatewayClientTransport
  - OpenClaw
  - randomUUID
initial_weight: 1.0
current_weight: 1.139
last_activated: 2026-06-03
access_count: 5
---

# 魔改版 vs 官方 SDK 差异对比

## 结论

`test-openclaw-sdk/src/sdk/` 是官方 `@openclaw/browser-sdk` 的原样复刻，不是从 Node SDK 魔改而来。功能与官方 browser-sdk 完全一致，唯一多出一行调试用 `debugger`（`client.ts:67`，须删除）。

## 三方关系

官方 monorepo（`openclaw-main-20260519`）中存在两个独立包：

| 包 | 路径 | 平台 |
|----|------|------|
| `@openclaw/sdk` | `packages/sdk/` | Node.js |
| `@openclaw/browser-sdk` | `packages/browser-sdk/` | 浏览器 |

魔改版 = `@openclaw/browser-sdk` 源码，import 扩展名从 `.js` 改为 `.ts`（Vite bundler 模式适配）。

## 唯一实质分叉：transport.ts

### Node SDK（`packages/sdk/src/transport.ts`）

- 依赖内部 `GatewayClient` 类（Node.js 封装），不直接操作 WebSocket
- `connect()` 调用 `client.start()`，`close()` 调用 `client.stopAndWait()`
- 支持 Node 专属选项：`bootstrapToken`、`deviceToken`、`tlsFingerprint`、`deviceIdentity`、`permissions`、`pathEnv`、`connectChallengeTimeoutMs`、`preauthHandshakeTimeoutMs`、`onReconnectPaused`

### browser-sdk / 魔改版（`src/sdk/transport.ts`）

- 直接 `new WebSocket(url)`，自实现：
  - 握手（`connect.challenge` → `sendConnect` → `hello-ok`）
  - 指数退避重连（800ms → ×1.7 → 15s）
  - 请求超时（pending Map + setTimeout）
- 不支持上述 Node 专属选项（浏览器平台不适用，属合理裁剪，非魔改遗漏）

## 其他文件差异

| 文件             | Node SDK vs browser-sdk                                     | browser-sdk vs 魔改版   |
| -------------- | ----------------------------------------------------------- | -------------------- |
| `client.ts`    | 仅 `randomUUID` 来源不同（`node:crypto` vs `crypto.randomUUID()`） | +1 行 `debugger`（须删除） |
| `types.ts`     | 完全相同                                                        | 完全相同                 |
| `normalize.ts` | 完全相同                                                        | 完全相同                 |
| `event-hub.ts` | 完全相同                                                        | 完全相同                 |
| `index.ts`     | 完全相同                                                        | 扩展名 `.js` → `.ts`    |

## 边界

- Node SDK 的设备认证（`bootstrapToken`/`deviceToken`）、TLS 指纹校验、权限声明在浏览器中无法实现，是平台边界，不是功能缺口。
- 魔改版 API 面（9 个 Namespace、Run/Session/Agent 实体、EventHub）与官方 browser-sdk 完全一致。

## 相关概念

[[sdk_architecture]] [[WebSocket 重连策略]]
