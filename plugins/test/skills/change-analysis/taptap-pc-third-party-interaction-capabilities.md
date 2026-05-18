# TapTap PC 主站 - 三方应用交互能力梳理

梳理范围：tap-main/pc（TapTap PC 客户端，含 `main/` Go 后端、`launcher/` CN Electron 前端、`launcher-intl/` 海外 Electron 前端、`sdk/tapsdk/` SDK Core/Loader、`overlay/` 游戏内覆盖层、`minigame/` 小游戏子进程、`emulator-connector/` Android 模拟器兼容 APK）与外部三方应用之间的全量交互能力及代码位置。

参考的 SDK 仓库：`/Users/taptap/StudioProjects/github/TapSDK-Monorepo/iOS` 中无 PC SDK；PC SDK 由本仓库 `sdk/tapsdk/`（Go Core）+ `sdk/tapsdk/loader/`（Rust Loader，输出 C ABI 头 `taptap_api.h` / `taptap_achievement.h` / `taptap_cloudsave.h` / `taptap_compliance.h` / `taptap_onlinegame.h`）共同构成；Unity 版本与 C++ 版本游戏统一对接此 C ABI。

更新时间：2026-05-18

---

## 一、SDK 调用 TapTap 主站的能力模块

> SDK 侧（游戏进程内）通过 **Loader（Rust，C ABI）→ Core（Go，gRPC client）→ Main（Go gRPC server，Windows Named Pipe）** 三层调用 TapTap PC 客户端。**MR 改动这些文件时需特别注意对外部 SDK 接入方（C++/Unity 游戏）的兼容性影响。**
>
> 与 Android/iOS 的关键区别：PC 没有 OS 级 Scheme/AIDL 限制，跨进程通道是 **Windows Named Pipe + gRPC**（macOS/Linux fallback：Unix domain socket + TCP `127.0.0.1:$TAPTAP_MAIN_GRPC_PORT`）。

### 1.1 SDK 启动 & 版本协商（TapSDK.Init）

**SDK 调用入口**：游戏调用 `TapSDK_Init(errMsg, pubKey)`（`sdk/tapsdk/loader/taptap_api.h:317`）→ Loader 加载 `tapsdk-core.dll` → Core `dialMain()` 建立 gRPC 连接 → `tapsdkpb.NewTapSDKClient(c).Init(InitRequest)`

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| gRPC 服务 | `tapsdk.TapSDK.Init`（`proto/tapsdk/tapsdk.proto:10`） |
| 主站实现 | `main/internal/api/tapsdk_grpc/server.go:60` |
| 接入逻辑 | `main/internal/service/tapsdk/tapsdk.go:40` → `client_api.PCSDKCore.SdkInit(ctx, ...)` 调用 server 端 |
| 进程校验 | `gamemgr.HasProcessID(req.ClientId, int(connInfo.ProcessID))`（验证调用方进程确实由 TapTap 启动） |
| Loader/Core 版本上报 | `InitRequest.tapsdk_loader_version` / `InitRequest.tapsdk_core_version` |
| 响应 | `InitResponse { client_id, app_id, openid, ownership_ticket, oauth_api_host, session_id, clock_skew, sdk_open_urls }` |

**MR 风险**：⚠️ 高
- `InitRequest` / `InitResponse` 字段 proto tag 编号不可改 — 所有线上 SDK 版本依赖
- `RequestResult` enum 取值不可改 — SDK 端用于错误码判定（Uninitialized / NoTapTapClient / TapTapClientOutdated / SdkFailed / TapTapClientNotLoggedIn / NetworkError）
- `InitMode` enum 取值不可改（REL=0 / DEV=1）
- 进程校验逻辑 `gamemgr.HasProcessID` 变更可能影响沙盒/SCE 启动的游戏判定

---

### 1.2 SDK 启动器检测 & 自动重启（TapSDK_RestartAppIfNecessary）

**SDK 调用入口**：游戏启动时 `TapSDK_RestartAppIfNecessary(clientID)`（`sdk/tapsdk/loader/taptap_api.h:309`） → Loader 检查环境变量 `TAPTAP_MAIN_GRPC_PORT` 或 IPC pipe 是否可连 → 不可连则启动 `taptap.exe taptap://taptap.com/app?app_id=...&client_id=...&auto_launch=yes&platform=pc`

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| URL Scheme | `taptap://taptap.com/...`（CN，OS 注册）/ `open-taptap-{client_id}://authorize`（Intl，浏览器 OAuth 回调专用） |
| URL_SCHEME 常量 | `launcher/src/shared/config.ts:7` — `taptap://taptap.com` |
| OAUTH_SCHEME 常量 | `launcher-intl/src/shared/config.ts:14` — `open-taptap-${OAUTH_CLIENT_ID}` |
| Intl Scheme 注册 | `launcher-intl/src/main/app.ts:109` — `app.setAsDefaultProtocolClient(OAUTH_SCHEME, ...)` |
| CN Scheme 卸载 | `setup/NSIS_SetupSkin/SetupScripts/TapTap_CN/ui_TapTap_setup.nsh:1813` — `DeleteRegKey HKCR "taptap"`（写入由 nsNiuniuSkin 插件完成） |
| 单实例 → handleArgv | `launcher/src/main/app.ts:462` `second-instance` 事件 → `handleArgv(argv)` → `launcherAPI.handleSecondInstance` |
| HandleSecondInstance RPC | `main/internal/api/tappc_http/launcher/launcher.go:84` |

**MR 风险**：⚠️ 高
- `taptap://taptap.com` URL Scheme（CN）和 `open-taptap-{client_id}://authorize`（Intl）均与 OS 注册绑定，**Scheme 字符串不可改**
- `auto_launch=yes` / `platform=pc` query 参数语义不可改 — SDK 已硬编码
- `handleArgv(argv)` 的 argv offset 计算（dev 模式 offset+1）变更可能漏掉 scheme

---

### 1.3 SDK OAuth 授权（TapUser_AsyncAuthorize）

**SDK 调用入口**：`TapUser_AsyncAuthorize(scopes)` / `TapUser_AsyncAuthorize_internal(...)`（`taptap_api.h:408/426`） → `tapsdkpb.NewTapSDKClient(c).Authorize(AuthorizeRequest)` → 通过 Stream 接收 `AuthorizeFinishedEvent`

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| gRPC 服务 | `tapsdk.TapSDK.Authorize`（`proto/tapsdk/tapsdk.proto:13`） |
| 主站实现 | `main/internal/api/tapsdk_grpc/server.go:129` |
| 触发渲染窗口 | `ws.Send(ctx, wspb.Command_TAPSDK_AUTHORIZE, ...)` — 通过 WebSocket 通道转发到 Electron 渲染进程 |
| Renderer 弹授权窗 | `launcher/src/main/features/auth/` 系列文件 |
| 完成事件 | `EventId_AuthorizeFinished = 2001` → `AuthorizeFinishedEvent { is_cancel, callback_uri, error, session_id }` |
| 关键字段 | `client_id` / `scope` / `response_type` / `redirect_uri` / `code_challenge` / `code_challenge_method` / `state` / `info` / `version` / `sdk_ua` / `session_id` |

**MR 风险**：⚠️ 高
- `AuthorizeRequest` 全部字段 proto tag 不可改（包括 sdk_ua=101、session_id=201 这种独立编号）
- `AuthorizeRequestResult` enum（Unknown/OK/Failed/InFlight）不可改
- `EventId_AuthorizeFinished = 2001` 不可改 — SDK 已硬编码事件 ID
- 渲染层授权窗口 → WebSocket 协议（`wspb.Command_TAPSDK_AUTHORIZE` / `Message_TAPSDK_AUTHORIZE`）变更需同步 launcher renderer

---

### 1.4 SDK 事件流（TapSDK.Stream + ListenEvent）

**SDK 调用入口**：Core 启动时 `tapsdkpb.NewTapSDKClient(c).Stream(...)` 建立双向流；按需 `ListenEvent(event_id)` 订阅特定事件

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| Stream 服务 | `tapsdk.TapSDK.Stream`（`proto/tapsdk/tapsdk.proto:14`） |
| 主站实现 | `main/internal/api/tapsdk_grpc/server.go:157` → `tapsdk_stream.Accept(stream)` |
| 事件订阅 | `tapsdk.TapSDK.ListenEvent` → `systemstate.ListenEvent(ctx, req)` |
| Stream 消息体 | `StreamMessage { event_id, authorize_finished, ownership_changed, trace_id, req_id, error_info, response, rsp_data }` |
| Stream 请求体 | `StreamRequest { event_id, trace_id, req_id, req_data }` |

支持的 EventId 范围（详见 `proto/tapsdk/tapsdk.proto:107-173`）：

| 范围 | 类别 | 关键事件 |
|------|------|---------|
| [1, 2000) | TapTap 平台事件 | `EventId_SystemStateChanged=1` / `EventId_OwnershipChanged=2` |
| [2001, 4000) | 用户事件 | `EventId_AuthorizeFinished=2001` |
| [4001, 6000) | DLC 事件 | `EventId_DLCPlayableStatusChanged=4001`（由 tapsdk-core 内部触发，不走 gRPC） |
| [6001, 7000) | 云存档事件 | `EventId_CloudSaveList=6001` … `EventId_CloudSaveGetCover=6006` |
| [7001, 8000) | 成就事件 | `EventId_AchievementUnlock=7001` / `EventId_AchievementIncrement=7002` |
| [8001, 9000) | 合规事件 | `EventId_ComplianceEnsureRealName=8001` / `EventId_ComplianceActionsEvent=8002` |
| [1000000001, 1000001000) | 联机游戏请求 | OnlineGame Connect/Disconnect/CreateRoom/MatchRoom/.../SendFrameInput/StopFrameSync |
| [1000001000, 1000002000) | 联机游戏通知 | OnlineGameServiceError/DisconnectNotification/EnterRoomNotification/.../SyncFrame |

**MR 风险**：⚠️ 高
- **EventId 整数值不可改、不可删** — SDK 端硬编码这些 ID 区间。新增事件只能在区间末尾追加
- `StreamMessage` / `StreamRequest` 字段 tag 不可改
- `SystemState` enum（Unknown/PlatformOnline=1/PlatformOffline=2/PlatformShutdown=3）不可改 — 游戏开发者会基于此做存档/退出决策
- 区间分配规则不可改 — `EventId_StreamRequest_Begin=1000000000` 是 SDK 路由判断分界

---

### 1.5 DLC 内购与所有权验证（TapApps_IsOwned / TapDLC_*）

**SDK 调用入口**：
- `TapApps_IsOwned()` / `TapDLC_IsOwned(dlc_id)` / `TapDLC_ShowStore(dlc_id)`（`taptap_api.h:388/444/451`）
- Loader 内部基于 RSA 签名验证 `ownership_ticket`（无需每次请求主站）；订单变更时主站通过 `EventId_OwnershipChanged` 推送新 ticket

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| Init 返回 | `InitResponse.ownership_ticket`（首次发放） |
| 刷新接口 | `clientapi.pcsdk.core.Core.RefreshOwnershipTicket`（`proto/apis/clientapi/pcsdk/core/core.proto`） |
| 安卓兼容 | `Core.AndroidOwnershipTicket(TYPE_GAME / TYPE_DLC)` — 用于模拟器内的 Android 游戏（见第十一章） |
| 事件 | `EventId_OwnershipChanged=2` + `OwnershipChangedEvent { ticket }`（`proto/tapsdk/tapsdk.proto:202`） |
| Store 跳转 | `TapDLC_ShowStore` → 通过 WS/Stream 通知 Electron 渲染层打开商店 |

**MR 风险**：⚠️ 高
- `OwnershipChangedEvent.ticket` 字段格式（RSA 签名结构）变更 → Loader 侧验签失败，DLC 立即不可用
- `RefreshOwnershipTicket` / `AndroidOwnershipTicket` 接口不可变更字段
- RSA 公钥（`pubKey` 参数，`TapSDK_Init` 传入）作为 SDK 与主站的信任根，变更需所有游戏重新打包

---

### 1.6 云存档（TapCloudSave_*）

**SDK 调用入口**：`TapCloudSave_AsyncList` / `AsyncCreate` / `AsyncUpdate` / `AsyncDelete` / `AsyncGetData` / `AsyncGetCover`

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| gRPC 服务 | `tapsdk.cloudsave.CloudSave`（`proto/tapsdk/cloudsave/cloudsave.proto`，6 个方法） |
| 注册 | `main/internal/api/tapsdk_grpc/cloudsave/server.go:18` |
| 业务 | `main/internal/service/tapsdk/cloudsave/` |
| 对应事件 | `EventId_CloudSaveList=6001` … `EventId_CloudSaveGetCover=6006` |

**MR 风险**：⚠️ 高 — RPC 方法签名 / 字段 tag 不可改；EventId 编号不可改

---

### 1.7 成就（TapAchievement_*）

| 项目 | 说明 |
|------|------|
| gRPC 服务 | `tapsdk.achievement.Achievement.Unlock / Increment`（`proto/tapsdk/achievement/achievement.proto`） |
| 注册 | `main/internal/api/tapsdk_grpc/achievement/server.go:16` |
| 服务端代理 | `proto/apis/tappc/tapsdk/achievement/achievement.proto`（同名服务，主站→服务端转发） |
| 对应事件 | `EventId_AchievementUnlock=7001` / `EventId_AchievementIncrement=7002` |
| 端内跳转 URI | `InitResponse.sdk_open_urls.achievement_my_list_url.uri`（PCSDKUrl，由服务端下发） |

**MR 风险**：⚠️ 高 — RPC 方法签名 / 字段 tag / EventId 不可改

---

### 1.8 合规认证 / 防沉迷（TapCompliance_*）

| 项目 | 说明 |
|------|------|
| C ABI 接口 | `TapCompliance_AsyncEnsureRealName` / `TapCompliance_EnableAntiAddiction` / `TapCompliance_CheckPaymentLimit` / `TapCompliance_SubmitPayment` |
| gRPC 服务 | `tapsdk.compliance.Compliance`（`proto/tapsdk/compliance/compliance.proto`，4 方法） |
| 注册 | `main/internal/api/tapsdk_grpc/compliance/compliance.go:18` |
| 服务端代理 | `proto/apis/tappc/tapsdk/compliance/compliance.proto`（CheckAccess/CheckPaymentLimit/SubmitPayment/GetGlobalConfig） |
| 当前合规模块列表 | `Launcher.ComplianceOpenClientIds`（HTTP GET `/launcher/compliance-open-client-ids`） |
| 对应事件 | `EventId_ComplianceEnsureRealName=8001` / `EventId_ComplianceActionsEvent=8002` |

**MR 风险**：⚠️ 高 — RPC 方法签名 / EventId 不可改；`trace_id`/`req_id` 字段（SDK 内请求追踪）含义不可改

---

### 1.9 联机游戏（TapOnlineGame_*）

| 项目 | 说明 |
|------|------|
| C ABI 接口 | 18 个 `TapOnlineGame_Async*` 方法（`taptap_onlinegame.h`） |
| 传输通道 | 全部走 `TapSDK.Stream`（`proto/tapsdk/tapsdk.proto:14`），不另起 gRPC service |
| 请求 EventId | `[1000000001, 1000001000)` 共 15 个（Connect/Disconnect/CreateRoom/MatchRoom/JoinRoom/.../SendFrameInput/StopFrameSync） |
| 通知 EventId | `[1000001000, 1000002000)` 共 13 个（ServiceError/DisconnectNotification/EnterRoomNotification/PlayerCustomStatusNotification/.../SyncFrame） |
| 主站实现 | `sdk/tapsdk/onlinegame.go`（452 行） |

**MR 风险**：⚠️ 高 — EventId 不可改；Stream 协议中 `req_id`（开发者生成）与 `trace_id`（内部）含义不可调换

---

### 1.10 SDK 调用记录（TapSDK.Record）

主站收集 SDK 侧 API 调用日志（最多 100 条/批），主站埋点上报。

| 项目 | 说明 |
|------|------|
| RPC | `tapsdk.TapSDK.Record` |
| 主站实现 | `main/internal/api/tapsdk_grpc/server.go:170` → `track.UploadEvent` |
| 消息体 | `RecordRequest { repeated RecordLog logs }` / `RecordLog { action, args[], timestamp }` |

**MR 风险**：🔶 中 — RecordLog 字段不可改

---

### 1.11 健康检查 & 会话校验

| RPC | 说明 |
|-----|------|
| `TapSDK.HealthCheck` | Loader 启动时探活；旧版本未实现 → 返回 `Unimplemented` 视为成功 |
| `TapSDK.SessionCheck` | 检查 SDK session 是否仍有效 |

**MR 风险**：🔶 中 — 删除 `HealthCheck` → 旧 Loader 无法判定连接（实现保留必要）

---

### 1.12 SDK Loader C ABI 公开符号（C++ / Unity 接入契约）

> **48 个 `T_API extern "C"` 导出符号** 来自 `sdk/tapsdk/loader/taptap_*.h`。这是游戏侧（C++/Unity Native Plugin）直接链接的 ABI，**符号名 / 函数签名 / 枚举取值不可改**。

| Header | 符号数 | 关键符号 |
|--------|--------|---------|
| `taptap_api.h` | 12 | `TapSDK_Init` / `TapSDK_Shutdown` / `TapSDK_RestartAppIfNecessary` / `TapSDK_GetClientID` / `TapSDK_RegisterCallback` / `TapSDK_UnregisterCallback` / `TapSDK_RunCallbacks` / `TapSDK_CreateRandomNumberGenerator` / `TapSDK_RandomInt` / `TapSDK_DestroyRandomNumberGenerator` / `TapApps_IsOwned` / `TapUser_AsyncAuthorize` / `TapUser_AsyncAuthorize_internal` / `TapUser_GetOpenID` / `TapDLC_ShowStore` / `TapDLC_IsOwned` |
| `taptap_onlinegame.h` | 17 | `TapOnlineGame_RunCallbacks` / 16 个 `TapOnlineGame_Async*` |
| `taptap_cloudsave.h` | 6 | `TapCloudSave_AsyncList` / `Create` / `Update` / `Delete` / `GetData` / `GetCover` |
| `taptap_compliance.h` | 4 | `TapCompliance_AsyncEnsureRealName` / `EnableAntiAddiction` / `CheckPaymentLimit` / `SubmitPayment` |
| `taptap_achievement.h` | — | `TapAchievement_*` |
| 枚举 | — | `TapSDK_Init_Result`（OK/FailedGeneric/NoPlatform/NotLaunchedByPlatform/PlatformVersionMismatch）/ `TapSDK_Result`（OK/Uninitialized/NoTapTapClient/.../NetworkError）/ `TapSDK_ErrorCode`（Success/Unknown/Unauthorized/.../InternalSdkError/.../CloudSave_*）|

**MR 风险**：⚠️ 高
- **C ABI 符号名 / 参数列表 / 返回类型 / `T_CALLTYPE` 调用约定不可改** — Unity Plugin 和 C++ 静/动态链接都已绑定
- 枚举取值不可改（特别是 `TapSDK_Init_Result_*` / `TapSDK_Result_*` / `TapSDK_ErrorCode_*`）— 游戏端 switch/case 已硬编码
- 新增能力必须新增符号，不可修改已有符号

---

### MR 速查：SDK 高风险文件

| 文件 | 所属能力 | 影响 |
|------|---------|------|
| `proto/tapsdk/tapsdk.proto` | 1.1 / 1.3 / 1.4 / 1.5 / 1.9 / 1.10 / 1.11 | ⚠️ 字段 tag、EventId、enum 取值不可改 |
| `proto/tapsdk/cloudsave/cloudsave.proto` | 1.6 | ⚠️ 6 个 RPC 方法签名 |
| `proto/tapsdk/achievement/achievement.proto` | 1.7 | ⚠️ Unlock/Increment 签名 |
| `proto/tapsdk/compliance/compliance.proto` | 1.8 | ⚠️ 4 个 RPC 方法签名 |
| `proto/apis/clientapi/pcsdk/core/core.proto` | 1.1 / 1.5 | ⚠️ SdkInit/RefreshOwnershipTicket/AndroidOwnershipTicket（含 TYPE_GAME / TYPE_DLC 枚举） |
| `sdk/tapsdk/loader/taptap_api.h` | 1.12 | ⚠️ C ABI 头：所有 `T_API` 符号、枚举取值、`T_CALLTYPE` 调用约定不可改 |
| `sdk/tapsdk/loader/taptap_achievement.h` / `taptap_cloudsave.h` / `taptap_compliance.h` / `taptap_onlinegame.h` | 1.7 / 1.6 / 1.8 / 1.9 | ⚠️ C ABI 头同上 |
| `main/internal/api/tapsdk_grpc/server.go` | 1.1 / 1.3 / 1.4 / 1.10 / 1.11 | ⚠️ `Init` 的 `gamemgr.HasProcessID` 校验、四个 handler 实现 |
| `main/internal/api/tapsdk_grpc/cloudsave/server.go` / `achievement/server.go` / `compliance/compliance.go` | 1.6 / 1.7 / 1.8 | ⚠️ 子服务注册 |
| `main/internal/service/tapsdk/tapsdk.go`（`tapsdk.Init`） | 1.1 | ⚠️ Init 落地实现 |
| `main/internal/service/process_mapping/detector.go` | 1.1 | 🔶 `hasProcessMapping` 实现，影响游戏 / SDK 进程绑定校验 |

---

## 二、IPC 通道与协议契约（Named Pipe + gRPC + HTTP + WS）

> PC 平台没有 Android 的 AIDL/iOS 的 URL Scheme 作为 OS 级的契约面 — **所有跨进程通信契约都汇聚到 Named Pipe 名称 + gRPC service descriptor + HTTP 路由 + WS 命令**。**重命名 pipe / 调整 gRPC 注册 / 删除 HTTP endpoint 等价 Android 删 AIDL 接口**。

### 2.1 Named Pipe 命名（CN / Global 分包）

| 常量 | CN 值 | Global 值 |
|------|-------|----------|
| `TapSDK_gRPC` | `tappc_cn_tapsdk_grpc` | `tappc_global_tapsdk_grpc` |
| `TapPC_HTTP` | `tappc_cn_http` | `tappc_global_http` |
| `TapPC_WS` | `tappc_cn_ws` | `tappc_global_ws` |
| `TapMiniGame_gRPC` | `tappc_cn_minigame_grpc` | `tappc_global_minigame_grpc` |

代码：
- `main/pkg/ipc_name/ipc_name_cn.go`（build tag `!region_global`）
- `main/pkg/ipc_name/ipc_name_global.go`（build tag `region_global`）
- 监听：`main/internal/pkg/app/servers.go:74-95`
- Windows pipe path：`\\.\pipe\<name>`（`main/pkg/ipc/win.go:135`）
- Unix domain socket fallback：`main/pkg/ipc/unix.go:31`

### 2.2 服务注册总览

**TapSDK gRPC**（`tappc_cn_tapsdk_grpc` / `tappc_global_tapsdk_grpc`）— 外部 SDK 调用入口：

| Service | 方法 | 文件 |
|---------|------|------|
| `tapsdk.TapSDK` | Init / ListenEvent / Authorize / Stream / Record / HealthCheck / SessionCheck | `main/internal/api/tapsdk_grpc/server.go:49` |
| `tapsdk.cloudsave.CloudSave` | List/Create/Update/Delete/GetData/GetCover | `main/internal/api/tapsdk_grpc/cloudsave/server.go:18` |
| `tapsdk.achievement.Achievement` | Unlock/Increment | `main/internal/api/tapsdk_grpc/achievement/server.go:16` |
| `tapsdk.compliance.Compliance` | EnsureRealName/EnableAntiAddiction/CheckPaymentLimit/SubmitPayment | `main/internal/api/tapsdk_grpc/compliance/compliance.go:18` |

**tappc HTTP**（`tappc_cn_http` / `tappc_global_http`）— Renderer 内部调用，**严格仅同进程**：

| Service | 主要 HTTP 路径 | 文件 |
|---------|-------------|------|
| `apis.tappc.auth.Auth` | `/auth/*` | `main/internal/api/tappc_http/auth/` |
| `apis.tappc.gamemgr.Gamemgr` | `/gamemgr/{get,list,download-size,compose,pause,resume,play,stop,show,add-desktop-shortcut,open-folder,migrate,running-details,stop-all-miniapps}` | `main/internal/api/tappc_http/gamemgr/` |
| `apis.tappc.kvstore.KVStore` | `/kvstore/{set,batch-set,get,batch-get,delete,list,buckets}` | `main/internal/api/tappc_http/kvstore/` |
| `apis.tappc.launcher.Launcher` | `/launcher/{shutdown,md5,handle-second-instance,upload-events,open-folder,list-drives,system-info,bring-window-to-front,compliance-open-client-ids}` | `main/internal/api/tappc_http/launcher/` |
| `apis.tappc.selfupdate.SelfUpdate` | `/self-update/*` | `main/internal/api/tappc_http/selfupdate/` |
| `apis.tappc.settings.Settings` | `/settings/{get,list,update}` | `main/internal/api/tappc_http/settings/` |
| `apis.tappc.tapsdk.TapSDK` | `/tapsdk/*` | `main/internal/api/tappc_http/tapsdk/` |
| `apis.tappc.emulator.Emulator` | `/emulator/{get-engine,uninstall-engine,install-engine,verify-engine,pause-install-engine,open-folder}` | `main/internal/api/tappc_http/emulator/` |
| `apis.tappc.instant_games_runtime.InstantGamesRuntime` | `/instant-games-runtime/{get,install}` | `main/internal/api/tappc_http/instant_games_runtime/` |
| `apis.tappc.webapi.WebAPI` | `/webapi/*`（独立的 `webapi_http` 服务器） | `main/internal/api/webapi_http/server.go:46` |

**Minigame gRPC**（`tappc_cn_minigame_grpc`）— Minigame 子进程与主进程通信（同版本绑定）：

| Service | 方法 | 文件 |
|---------|------|------|
| `minigame.MiniGame` | HealthCheck / GameLifecycle / WatchCommands(stream) / UploadEvents | `main/internal/api/minigame_grpc/service.go:24` |
| `minigame.ApiService` | Request（透传 HTTP API） | `main/internal/api/minigame_grpc/service.go:25` |

### 2.3 进程身份校验（关键安全契约）

| 通道 | 校验规则 | 代码 |
|------|---------|------|
| tappc HTTP | 仅同进程（PID 匹配 `os.Getpid()`）；`HandleSecondInstance` 例外 | `main/internal/api/tappc_http/server.go:92` `withVerifyRequestProcess` |
| TapSDK gRPC | `gamemgr.HasProcessID(client_id, pid)`（仅 REL 模式校验） | `main/internal/api/tapsdk_grpc/server.go:66` |
| Windows pipe ACL | 允许非管理员访问由管理员创建的 pipe | `main/pkg/ipc/win.go:23` |

**MR 风险**：⚠️ 高
- Pipe 名称变更 → 同时影响 Loader（写死的常量）、Launcher（启动时 dial）、Minigame 子进程；CN/Global 必须同步变更
- gRPC service descriptor proto package 路径（如 `tapsdk.cloudsave`）变更 → 编译期断 + 旧客户端反射查找失败
- HTTP endpoint 路径变更需同步 proto `(apis.http)` annotation；**严禁手动 `http.HandleFunc` 注册**（绕过 `withVerifyRequestProcess`）— `main/CLAUDE.md` 已强调
- 删除 `withVerifyRequestProcess` 中的 PID 校验 = 任意进程可调用 tappc HTTP，安全漏洞
- 删除 `gamemgr.HasProcessID` 检查 = 任意游戏可冒名调用其他 client_id

---

## 三、端内容器 JS / Native API 契约（Minigame / InstantGames Runtime / Emulator）

> PC 主站托管运行第三方代码的容器：**Minigame**（独立 Electron 子进程跑 H5 小游戏）、**InstantGames Runtime**（独立运行时下发）、**Emulator**（Android 模拟器 + `emulator-connector` APK 提供 Android 兼容层）。改这些容器的 Bridge / API 等价 Android `ISandboxCallTapService.aidl` 改动。

### 3.1 Minigame Bridge（主进程 ↔ 小游戏 H5）

| 项目 | 说明 |
|------|------|
| 主进程入口 | `minigame/src/main/` |
| Renderer | `minigame/src/renderer/` |
| Native | `minigame/src/rust/napi/` + `minigame/src/go/` |
| Bridge 脚本（注入到游戏 H5） | `minigame/bridge-scripts/entry.taph5a.js` / `init-validation.js` / `pre-init.js` |
| 主进程 ↔ Launcher 通信 | `minigame.MiniGame` gRPC（`tappc_cn_minigame_grpc`）— GameLifecycle / WatchCommands(stream) / UploadEvents |
| 主进程 ↔ H5 API 代理 | `minigame.ApiService.Request` — 透传 HTTP API |
| Renderer ↔ Main API | `minigame/src/preload/` |
| 控制指令 | `GameCommand { type, app_id }`，`type ∈ {"stop_game"}` |
| 生命周期上报 | `GameLifecycleRequest { app_id, miniapp_id, status }`，`status ∈ {"playing","stopped"}` |

**MR 风险**：⚠️ 高
- `entry.taph5a.js` 中的 cross-object 协议（`$js_handle` / `$native_handle` / `$$` / `$#` 编码）变更 → 所有小游戏失效
- `GameCommand.type` 取值不可改 — Launcher 与 Minigame 已硬编码
- `GameLifecycleRequest.status` 字符串取值不可改

### 3.2 InstantGames Runtime

| 项目 | 说明 |
|------|------|
| 服务 | `apis.tappc.instant_games_runtime.InstantGamesRuntime`（Get / Install） |
| 主站实现 | `main/internal/api/tappc_http/instant_games_runtime/` |
| 配置 | `main/internal/settings/other.go:37` — `ReleasePlatformInstantGamesRuntimeAppID()` |
| HTTP 路径 | `GET /instant-games-runtime/get` / `POST /instant-games-runtime/install` |

**MR 风险**：🔶 中 — Runtime 资源版本 / app_id 配置变更影响所有小游戏

### 3.3 Emulator + emulator-connector（Android 兼容面）

> **PC 平台特有的「Android 兼容层」**：模拟器（MuMu 等）内运行 Android 游戏时，`emulator-connector.apk`（Android APK）注入到模拟器，对外暴露与 Android TapTap 主站**完全等价的 Action / AIDL / Activity**，让原本接入 Android TapSDK 的游戏在 PC 模拟器内能正常工作。

| 项目 | 说明 |
|------|------|
| 模拟器引擎管理 | `apis.tappc.emulator.Emulator` gRPC（GetEngine/InstallEngine/UninstallEngine/VerifyEngine/PauseInstallEngine/OpenFolder） |
| 主站实现 | `main/internal/api/tappc_http/emulator/` |
| 引擎安装 | 通过 `composer` 下载 + 校验 |
| 模拟器内 APK | `emulator-connector/app/`（Gradle Android 工程） |
| 入口类 | `emulator-connector/app/src/main/java/com/taptap/connector/ConnectorActivity.kt` |

**emulator-connector 对外暴露的 Action / Service**（与 Android TapTap 主站一致）：

| Action / Service | 等价 Android 主站能力 | AIDL |
|------------------|--------------------|------|
| `com.taptap.sdk.action` / `com.taptap.global.sdk.action`（Activity） | SDK 登录授权（XDSDK → TapTapSdkActivity） | — |
| `com.play.taptap.billing.CheckLicenseAct`（Activity） | 授权检查兜底 | — |
| `com.play.taptap.billing.InAppBillingAct`（Activity） | DLC 内购 | — |
| `com.play.taptap.AntiAddiction.Action`（Activity） | 老版本防沉迷 | — |
| `com.play.taptap.service.InAppBillingService`（Service） | 购买授权 AIDL | `IInAppBillingService.aidl` / `ICallback.aidl` |
| `com.play.taptap.AntiAddictionService.BIND`（Service） | 老版本防沉迷 AIDL | `IAntiAddictionInterface.aidl` / `IAntiAddictionInfoCallback.aidl` |
| `ACTION_SEND_MULTIPLE`（图片分享接收） | tap-share 图片分享 | — |
| `android.intent.action.VIEW`（Scheme 跳转） | DeepLink 路由 | — |

**PC 端联动调用**：模拟器内 APK 收到这些 AIDL 调用后 → 通过 ADB/socket 转回 PC 主进程 → `client_api.PCSDKCore.AndroidOwnershipTicket(TYPE_GAME/TYPE_DLC)`（`proto/apis/clientapi/pcsdk/core/core.proto`）查询所有权

**MR 风险**：⚠️ 高（同 Android 主站对应能力）
- emulator-connector 的 Action 字符串 / AIDL 文件 / Activity 类名**必须与 Android TapTap 主站同步**（参考 Android 文档 1.2/1.3/1.4/1.6/1.7.2）
- `corepb.AndroidOwnershipTicketRequest.Type` 枚举（TYPE_GAME / TYPE_DLC）不可改
- `IInAppBillingService.aidl` / `IAntiAddictionInterface.aidl` 方法签名不可改 — 模拟器内游戏接入的 Android TapSDK 版本可能很老

### 3.4 容器契约速查

| 文件 | 影响 |
|------|------|
| `minigame/bridge-scripts/entry.taph5a.js` | ⚠️ Cross-object 编码协议，所有小游戏共享 |
| `proto/minigame/minigame.proto` | ⚠️ GameCommand/GameLifecycle 协议 |
| `proto/minigame/api/api.proto` | ⚠️ ApiService.Request 透传协议 |
| `emulator-connector/app/src/main/AndroidManifest.xml` | ⚠️ 8 个 exported 组件 + Action 字符串 |
| `emulator-connector/app/src/main/aidl/**/*.aidl` | ⚠️ 4 个 AIDL 接口，方法签名不可改 |
| `proto/apis/clientapi/pcsdk/core/core.proto` | ⚠️ AndroidOwnershipTicket 接口 + TYPE_GAME/TYPE_DLC 枚举 |
| `main/internal/service/android_gamemgr/emulator/connector*.go` | 🔶 PC ↔ emulator 桥接实现 |

---

## 四、URL Scheme / OAuth 回调（OS 注册的对外入口）

### 4.1 CN：`taptap://taptap.com/...`

| 项目 | 说明 |
|------|------|
| Scheme 常量 | `launcher/src/shared/config.ts:3-7` — `URL_PROTOCOL='taptap'` / `URL_HOST='taptap.com'` / `URL_SCHEME='taptap://taptap.com'` |
| OS 注册 | Windows 注册表 `HKCR\taptap`（由 nsNiuniuSkin NSIS 插件写入，卸载时由 `setup/NSIS_SetupSkin/SetupScripts/TapTap_CN/ui_TapTap_setup.nsh:1813` `DeleteRegKey HKCR "taptap"` 清理） |
| 进程接入 | `taptap.exe taptap://...` → Windows 启动新实例 → `requestSingleInstanceLock` → 已有实例 `second-instance` 事件 → `handleArgv(argv)` |
| 解析 | `launcher/src/main/features/app/protocol.ts:handleArgv` / `handleSchemeUri` |
| 通用 scheme handler | `launcher/src/shared/features/client-url/scheme-handler.ts`（CN / Intl 共享） |
| Webview 内链接拦截 | `launcher/src/main/features/web-view/scheme-handler.ts` |

### 4.2 Intl：`open-taptap-{client_id}://authorize`（OAuth 浏览器回调专用）

| 项目 | 说明 |
|------|------|
| 常量 | `launcher-intl/src/shared/config.ts:14` — `OAUTH_SCHEME = open-taptap-${OAUTH_CLIENT_ID}` |
| 注册 | `launcher-intl/src/main/app.ts:109` — `app.setAsDefaultProtocolClient(OAUTH_SCHEME, ...)` |
| 回调处理 | `launcher-intl/src/main/features/auth/oauth-pipe.ts` |
| 用途 | 用户在系统浏览器完成 OAuth 后浏览器跳回 `open-taptap-{clientID}://authorize?code=...&state=...` 唤起 launcher-intl |

**MR 风险**：⚠️ 高
- CN 的 `taptap` Scheme 名 + Host `taptap.com` 不可改 — OS 注册 + 服务端 wakeup link + SDK 1.2 写死
- Intl 的 `OAUTH_CLIENT_ID` 不可改 — 与 Auth 服务端配置绑定
- `URL_SCHEME` 与 `URL_HOST` 拼装规则变更影响所有 scheme path 解析（`URL_SCHEME → URL_WEB` 替换在 `scheme-handler.ts:57`）

---

## 五、Scheme 路由表契约（scheme-handler.ts）

> 等价 Android `SchemePath.kt` 路由表 / iOS `TapPageInsideIdentifier`。**已上线 pathname 不可删除、不可重命名 — SDK / 服务端 dispatch / Web 唤端、邮件链接、推送 payload、Widget（macOS 无）都已写死**。

### 5.1 路由表定义

| 项目 | 说明 |
|------|------|
| 路由解析 | `launcher/src/shared/features/client-url/scheme-handler.ts`（共享给 CN + Intl） |
| 注册的 pathname 总数 | **17 个**（直接 `if (pathname === ...)` 判定） |
| Vue 路由名映射 | `launcher/src/shared/router-config.ts`（`RouterNames` enum） |
| 返回类型 | `route`（Vue 路由跳转）/ `web_url`（外部 Web URL）/ `native`（端内 Native action） |

### 5.2 已上线 pathname 清单

| pathname | 类型 | 描述 | 主站承接 |
|----------|------|------|---------|
| `/recommend` | route | 推荐页 | RouterNames.Recommend |
| `/` / `/library` | route | 默认/游戏库 | RouterNames.AppLib |
| `/site` | route | 官方站 | RouterNames.OfficialSite |
| `/app` | route | 游戏详情（支持 `auto_launch` / `auto_download` query） | RouterNames.AppDetail（含特殊 `auto_download` 处理） |
| `/pc-devtool` | route | PC 开发者工具 | — |
| `/ranking` | route | 排行榜 | RouterNames.Ranking |
| `/collection` | route | 合集 | — |
| `/to` | web_url | 跳转 web url | `openWebView` / `RouterNames.HomeWebview` |
| `/moment` | route | 动态详情 | — |
| `/hashtag` | route | 话题 | — |
| `/group` | route | 论坛 | — |
| `/game_record/bind` | route | 战绩绑定 | — |
| `/user_center` | route | 用户中心 | — |
| `/close-webview` | native | 关闭授权窗口 + 可选 `complete=1` 刷新 profile | `destroyCustomWindow` / `refreshUserProfile` |
| `/confirm_order` | native | 确认订单（DLC 内购）— 入参 `dlc_id / app_id / game_hwnd / client_id` | `confirmOrder` |
| `/steam_account_data_bind` | native | Steam 账号数据绑定 | `openSteamBind` |
| `/` / `/index`（在 OfficialSite 分支） | route | 官方站首页 | RouterNames.OfficialSite |

### 5.3 query 参数契约

| 参数 | 用途 | 写死位置 |
|------|------|---------|
| `auto_launch=yes` | `/app` 路径下自动启动游戏 | SDK 1.2 / 服务端 dispatch |
| `auto_download=yes\|true` | `/app` 路径下自动下载 | 服务端 dispatch |
| `client_id` | 无 app_id 时通过 SDK 反查 app_id | SDK 1.2（启动 launcher 时携带） |
| `app_id` / `dlc_id` / `game_hwnd` | `/confirm_order` native action 入参 | DLC 1.5 |
| `request_id` / `request_type` | `/steam_account_data_bind` native action 入参 | 战绩绑定 |
| `complete=1` | `/close-webview` 完成实名后刷新 profile | 实名 1.8 |
| `track_data_referrer` | JSON，埋点 referrer 透传 | 埋点系统 |

**MR 风险**：⚠️ 高
- 已上线 pathname **任一删除或重命名** → 对应 SDK / 服务端 dispatch / 推送 payload / 邮件链接全部断链 — 等价 Android `SchemePath.kt` 已上线 path 锁定
- `native` action（`close-webview` / `confirm-order` / `steam-bind`）的入参 key 不可改
- `RouterNames` enum 值变更需同步 `router-config.ts` + Vue router 注册
- CN/Intl 共享此文件，**变更影响双端**

### 5.4 安全域白名单（服务端下发）

| 白名单 | 来源 | 用途 |
|-------|------|------|
| `secure_domains` | `Config.TermsV2` 服务端下发 → `configTerms.secure_domains` | TapTapAPI JSBridge 准入（`isSecureDomain`） |
| `forum_webview_url_whitelist` | 同上 → `configTerms.forum_webview_url_whitelist` | 论坛内 WebView URL pattern 白名单 |
| `DEFAULT_WEBVIEW_DOMAIN_WHITELIST` | `launcher/src/shared/config.ts:22-81` 硬编码 60+ 域名 | WebView 默认可打开域名（合作伙伴 / 问卷 / 厂商域名） |

**MR 风险**：⚠️ 高
- `secure_domains` 服务端下发但客户端 `isSecureDomain` 逻辑变更需同步 — 删除域名等于 SDK 内 H5 JSBridge 失效
- `DEFAULT_WEBVIEW_DOMAIN_WHITELIST` 添加/删除域名需走合作伙伴流程

---

## 六、Electron JSBridge（TapTapAPI / TapApiAction IPC）

### 6.1 TapTapAPI（contextBridge 暴露给 WebView 内 H5）

| 项目 | 说明 |
|------|------|
| Preload 实现 | `launcher/src/preload/shared/tap-tap-api.ts`（249 行） / `launcher-intl/src/preload/shared/` |
| 暴露方式 | `contextBridge.exposeInMainWorld('TapTapAPI', TapTapAPI)`（`launcher/src/preload/tapapi.ts:10`） |
| Renderer → Main 通道 | `ipcRenderer.invoke(TapApiAction.GET, { action, payload })` |
| Main 注册 | `launcher/src/main/features/window/taptap-api.ts:80` `ipcMain.handle(TapApiAction.GET, ...)` |
| 域名校验 | `isSecureDomain(url)` 拒绝非白名单（`launcher/src/main/features/app/taptap.ts:85`） |
| 同步通道 | `ipcRenderer.sendSync(TapApiAction.GET, ...)`（仅 `tapEnv` / `getClientXUA`） |

### 6.2 TapApiAction / TapApiMessageAction enum（`launcher/src/shared/types/tapapi.ts`）

| Action | 说明 |
|--------|------|
| `TapApiAction.GET` = `'tapapi:get'` | 主 IPC channel |
| `TapApiAction.HANDLE` = `'tapapi:handle'` | 备用 |
| `TapApiMessageAction.AuthFirstParty` = `'tapapi:auth:first-party'` | 第一方授权 |
| `TapApiMessageAction.WindowShow` = `'tapapi:window:show'` | 显示窗口 |
| `TapApiMessageAction.ToastShow` = `'tapapi:toast:show'` | Toast 提示 |
| `TapApiMessageAction.ProxyWebTrackLogs` = `'tapapi:proxy-web-track-logs'` | H5 埋点透传 |
| `TapApiMessageAction.CloseWebView` = `'tapapi:close-webview'` | 关闭 WebView |
| `TapApiMessageAction.VerifySuccess` = `'tapapi:verify-success'` | 实名认证成功通知 |
| `TapApiMessageAction.DirectDelivery` = `'tapapi:direct-delivery'` | 礼包直发 |
| `TapApiMessageAction.OpenBrowser` = `'tapapi:open-browser'` | 打开外部浏览器 |
| `TapApiMessageAction.ForceShowWebView` = `'tapapi:force-show-webview'` | 强制显示 WebView |
| `TapApiMessageAction.RequestClientLogUrl` = `'tapapi:request-client-log-url'` | 上传日志 |
| `TapApiMessageAction.TapEnv` = `'tapapi:tap-env'` | 获取 env（同步） |
| `TapApiMessageAction.GetClientXUA` = `'tapapi:get-client-xua'` | 获取 XUA（同步） |
| `TapApiMessageAction.GetAppStatus` = `'tapapi:get-app-status'` | 获取本机 app 状态（异步通过 `notifyAppStatusChanged` 回调） |
| `TapApiMessageAction.OpenApp` = `'tapapi:open-app'` | 打开游戏 |

### 6.3 TapTapAPI 公开 JS 函数（exposed via contextBridge）

来自 `launcher/src/preload/shared/tap-tap-api.ts:182-234`：

| 函数 | 说明 |
|------|------|
| `getClientLoginState()` | 返回 '0'/'1'，启动器必为 '1' |
| `getLoginCertificate(payload)` | 触发 AuthFirstParty |
| `showToast(message)` | Toast |
| `showWeb()` / `closeWebView()` / `forceShowWebView()` | 窗口控制 |
| `verifySuccess()` | 实名认证通过通知 |
| `tapLog(logStr)` | H5 埋点透传 |
| `directDelivery(payload)` | 礼包直发 |
| `openBrowser(url)` | 系统浏览器打开 URL |
| `openApp(payload)` / `getAppStatus(payload)` | 启动游戏 / 查游戏状态 |
| `tapEnv()` / `getClientXUA()` / `getTheme()` / `getGameScene()` | 同步取信息 |
| `requestClientLogUrl()` | 上传日志 |
| `actionList()` | 返回所有可用 action 名 |
| `login` / `toggleShareBtn` / `openShareWindow` / `toggleNavbar` / `copyToPasteboard` / `getSMDeviceId` / `activityCheckIn` / `toggleWebContentAutoMoveUp` | 兼容 stub（返回空，保留 API 表面避免 H5 调用报错） |

### 6.4 Preload 文件矩阵

| Preload | 暴露对象 | 用途 |
|---------|---------|------|
| `tapapi.ts` | `window.TapTapAPI` | 标准 WebView 通用 API |
| `webview.ts` | `window._ipc` | 内置 WebView（论坛/直发等） |
| `cloud-game-webview.ts` | `window.TapCloudGame` | 云玩游戏 WebView 专用 API |
| `forum-webview.ts` / `home-webview.ts` / `official-site-webview.ts` | — | 各业务 WebView 定制 |
| `friends-panel.ts` / `im.ts` / `notification.ts` / `direct-delivery.ts` / `message-notification.ts` / `tap-maker.ts` | — | 各窗口专用 |
| `overlay.ts` | `window._ipc` | 游戏内覆盖层 UI |
| `cloud-game.ts` / `browser-view.ts` | — | 容器/视图通用 |

**MR 风险**：⚠️ 高
- `contextBridge.exposeInMainWorld('TapTapAPI', ...)` 暴露的对象名 `TapTapAPI` 不可改 — 与 iOS/Android 端 WebView H5 一致协议
- `TapApiMessageAction` enum 字符串值（如 `'tapapi:close-webview'`）不可改 — preload 与 main 双侧硬编码
- `TapCloudGame` 全局对象（云玩）名不可改
- `TapApiAction.GET = 'tapapi:get'` IPC channel 名不可改
- `isSecureDomain` 域名白名单变更影响所有 H5 JSBridge 可用性
- 公开的 stub 函数（`login` / `toggleShareBtn` 等）不可删 — H5 端可能调用，删除会导致 H5 报 `undefined is not a function`

---

## 七、推送 / 通知

| 项目 | 说明 |
|------|------|
| 通知 API | Electron `Notification`（无第三方厂商推送通道） |
| 通知唤起 URI | `launcher/src/main/features/app/notification.ts:38` — 点击通知用 `taptap://` URI 唤起 |
| 推送跳转分发 | 经 `handleSchemeUri` 走第五章路由表 |

**MR 风险**：🔶 中 — 通知 payload 中的 `uri` 字段是服务端推送协议，变更需服务端同步

---

## 八、桌面快捷方式 / 系统集成

| 能力 | API | 代码 |
|------|-----|------|
| 添加桌面快捷方式 | `Gamemgr.AddDesktopShortcut`（HTTP `POST /gamemgr/add-desktop-shortcut`） | `proto/apis/tappc/gamemgr/gamemgr.proto` |
| 打开本地文件夹 | `Gamemgr.OpenFolder` / `Emulator.OpenFolder` / `Launcher.OpenFolder` | 三个独立 RPC |
| 列出系统驱动器 | `Launcher.ListDrives`（`GET /launcher/list-drives`） | — |
| 系统信息 | `Launcher.SystemInfo` | — |
| 窗口前置 | `Launcher.BringWindowToFront` | — |
| 安装 / 卸载 | NSIS 安装脚本 `setup/NSIS_SetupSkin/SetupScripts/TapTap_CN/`、`/TapTap_Intl/` | — |

**MR 风险**：🔶 中 — RPC 接口 / NSIS 注册表项是用户系统状态契约

---

## 九、Overlay 覆盖层（游戏进程注入 + Named Pipe + DXGI 共享纹理）

> Launcher 通过 `taptap_overlay_injector.exe` 把 `taptap_overlay.dll` 注入到游戏进程 → 在游戏 Present 调用上 Hook 渲染覆盖层 UI → Electron OSR 在 Launcher 端渲染 UI 内容 → 通过 **DXGI Shared Texture（D3D11，GPU 零拷贝）** + **Named Pipe（控制消息 / 输入转发）** 跨进程传递。

| 项目 | 说明 |
|------|------|
| 注入端 | `taptap_overlay_injector.exe`（`launcher/electron-builder.config.js:104`） |
| 游戏端 DLL | `taptap_overlay.dll` / `taptap_overlay.node`（`launcher/electron-builder.config.js:100`） |
| Native 端代码 | `overlay/overlay-native/` |
| Electron 端代码 | `overlay/overlay-electron-native/` |
| IPC 客户端（游戏 DLL 端） | `overlay/overlay-native/src/ipc/simple_ipc_client.cpp` |
| Pipe 路径 | `\\.\pipe\<server_name>`（`simple_ipc_client.cpp:156`） |
| 控制协议 | `SendMsg(string)` / `SetMessageCallback(callback)` — 字符串消息（具体格式见 overlay docs） |
| 传输方式 | D3D11 → DXGI Shared Texture（GPU 零拷贝）；OpenGL → CPU SharedMemory（fallback，暂不可用） |
| Hook 方法 | Present Hook（D3D11） |
| 显隐快捷键 | F12 |

**MR 风险**：⚠️ 高
- `simple_ipc_client.h` 公开 API（`Connect` / `Disconnect` / `IsConnected` / `SendMsg` / `SetMessageCallback` / `SetAutoReconnect` / `SetConnectionStateCallback`）不可改 — 游戏内 DLL 已硬编码
- Named Pipe 命名规则变更 → 注入到老版本游戏进程的 DLL 找不到 pipe
- 消息字符串协议（`SendMsg` 传输内容格式）变更需双端同步
- DXGI Shared Texture handle 格式变更需要协调 Electron OSR 端

---

## 十、WebSocket 通道（`tappc_cn_ws`）

> Launcher 主进程 ↔ Renderer 的实时事件通道，部分 SDK 事件（如授权弹窗、TAPSDK_INIT 等）也通过此通道转发到 Renderer。

| 项目 | 说明 |
|------|------|
| Pipe | `tappc_cn_ws` / `tappc_global_ws`（Named Pipe 上跑 WebSocket） |
| 监听 | `main/internal/pkg/app/servers.go:79` |
| 命令枚举 | `wspb.Command_*`（`proto/apis/tappc/m/ws/ws.proto`） |
| 关键命令 | `TAPSDK_INIT` / `TAPSDK_AUTHORIZE` |
| 消息体 | `Message_TAPSDK_INIT` / `Message_TAPSDK_AUTHORIZE` 等 |

**MR 风险**：🔶 中 — wspb.Command enum 取值不可改；TAPSDK_AUTHORIZE 字段对接渲染层授权窗口逻辑

---

## 十一、Composer 下载 / 安装协议

> 游戏下载 / 更新 / 校验由独立的 `composer/` 模块负责。

| 服务 | 说明 |
|------|------|
| `apis.clientapi.apk.Apk` | `Predownload` / `Detail` / `PatchesV2` / `PatchesV3` / `DetailWithUser` |
| `apis.clientapi.pcpackage.PcPackage` | `DetailV2` / `DetailByVersionV2` / `Detail` / `Patches` |
| `apis.clientapi.pcgame.PcGame` | `ProcessMapping`（游戏进程映射） |
| `apis.tappc.m.Composer` enum | `Action`（NONE/INSTALL/UPDATE/VERIFY/PRE_DOWNLOAD/.../UNINSTALL）/ `Status`（UNKNOWN/PREPARING/DOING/PAUSED/FAILED/COMPLETED） |
| 服务端 client API（PCSDKCore） | `HealthCheck` / `SdkInit` / `RefreshOwnershipTicket` / `AndroidOwnershipTicket` |

**MR 风险**：🔶 中
- `Composer.Action` / `Composer.Status` enum 取值不可改 — Renderer UI / 埋点 / 服务端字段同步依赖
- `PcGame.ProcessMapping` 返回 `process_name` / `signer_name` / `window_title` 字段不可改 — Overlay 注入依赖此映射判定目标进程

---

### MR 速查：高风险文件总表

| 文件 | 影响 |
|------|------|
| `proto/tapsdk/tapsdk.proto` | ⚠️ SDK gRPC 主入口，EventId / enum 取值 / 字段 tag 全部不可改 |
| `proto/tapsdk/cloudsave/*.proto` / `achievement/*.proto` / `compliance/*.proto` | ⚠️ SDK 子服务 RPC 签名 |
| `proto/apis/clientapi/pcsdk/core/core.proto` | ⚠️ PCSDKCore（SdkInit / RefreshOwnershipTicket / AndroidOwnershipTicket + TYPE_GAME/TYPE_DLC 枚举） |
| `proto/minigame/minigame.proto` / `api/api.proto` | ⚠️ 小游戏容器协议 |
| `proto/apis/tappc/launcher/launcher.proto` | ⚠️ Launcher HTTP API（9 个），HandleSecondInstance 是 OS scheme 接入点 |
| `proto/apis/tappc/gamemgr/gamemgr.proto` | ⚠️ 游戏管理 14 个 RPC（Compose/Play/Stop/AddDesktopShortcut/...） |
| `proto/apis/tappc/m/tappc.proto` | ⚠️ Composer.Action / Composer.Status 取值 |
| `sdk/tapsdk/loader/taptap_api.h` 等 5 个 .h | ⚠️ **48 个 C ABI 符号 + 枚举取值 + T_CALLTYPE 调用约定** — C++/Unity 游戏静/动态链接 ABI |
| `main/pkg/ipc_name/ipc_name_cn.go` / `ipc_name_global.go` | ⚠️ Pipe 名称（4 个常量），CN/Global 必须同步 |
| `main/internal/api/tapsdk_grpc/server.go` | ⚠️ Init 的进程校验、四个 handler |
| `main/internal/api/tapsdk_grpc/{cloudsave,achievement,compliance}/server.go` | ⚠️ 子服务注册 |
| `main/internal/api/tappc_http/server.go` | ⚠️ `withVerifyRequestProcess` PID 校验是 tappc HTTP 安全契约，不可删 |
| `main/internal/api/tappc_http/launcher/launcher.go` | ⚠️ HandleSecondInstance 实现，OS scheme → 路由分发起点 |
| `main/internal/service/tapsdk/tapsdk.go` | ⚠️ SdkInit 落地 |
| `main/internal/service/process_mapping/detector.go` | 🔶 进程绑定校验，影响沙盒/SCE/模拟器场景 |
| `main/internal/service/android_gamemgr/emulator/connector*.go` | 🔶 PC ↔ emulator-connector 桥接 |
| `launcher/src/shared/config.ts` | ⚠️ `URL_PROTOCOL='taptap'` / `URL_HOST='taptap.com'` / `URL_SCHEME` 拼装规则 + `DEFAULT_WEBVIEW_DOMAIN_WHITELIST` 60+ 域名 |
| `launcher-intl/src/shared/config.ts` | ⚠️ `OAUTH_SCHEME = open-taptap-${OAUTH_CLIENT_ID}` |
| `launcher-intl/src/main/app.ts:109` | ⚠️ `setAsDefaultProtocolClient(OAUTH_SCHEME, ...)` OS 注册 |
| `launcher/src/main/app.ts:462` `second-instance` handler | ⚠️ OS scheme 唤起入口，handleArgv 调用 |
| `launcher/src/main/features/app/protocol.ts` | ⚠️ `handleArgv` / `handleSchemeUri` 实现 — pendingSchemeUri + native action 分发 |
| `launcher/src/shared/features/client-url/scheme-handler.ts` | ⚠️ **路由表契约文件**：17 个 pathname + native action 入参 schema — CN/Intl 共享 |
| `launcher/src/shared/router-config.ts` | ⚠️ RouterNames enum + Vue 路由映射 |
| `launcher/src/preload/shared/tap-tap-api.ts` | ⚠️ TapTapAPI 公开 JS 函数清单（contextBridge 暴露） |
| `launcher/src/main/features/window/taptap-api.ts` | ⚠️ ipcMain handler，TapApiMessageAction 分发 |
| `launcher/src/shared/types/tapapi.ts` | ⚠️ TapApiAction / TapApiMessageAction 字符串枚举 |
| `launcher/src/main/features/app/taptap.ts:isSecureDomain` | ⚠️ JSBridge 准入校验，域名白名单（服务端 + 本地） |
| `setup/NSIS_SetupSkin/SetupScripts/TapTap_CN/ui_TapTap_setup.nsh` | ⚠️ CN 安装时写入 `HKCR\taptap`（卸载时 `DeleteRegKey HKCR "taptap"`） |
| `setup/NSIS_SetupSkin/SetupScripts/TapTap_Intl/ui_TapTap_setup.nsh` | ⚠️ Intl 安装脚本 |
| `minigame/bridge-scripts/entry.taph5a.js` | ⚠️ 小游戏 cross-object 协议 |
| `emulator-connector/app/src/main/AndroidManifest.xml` | ⚠️ 8 个 exported 组件 + Action 字符串（必须与 Android TapTap 主站同步） |
| `emulator-connector/app/src/main/aidl/com/play/taptap/service/IInAppBillingService.aidl` | ⚠️ 等价 Android 主站 AIDL，方法签名不可改 |
| `emulator-connector/app/src/main/aidl/com/play/taptap/service/antiAddiction/IAntiAddictionInterface.aidl` | ⚠️ 同上 |
| `overlay/overlay-native/src/ipc/simple_ipc_client.h` | ⚠️ Overlay 注入端 C++ API（公开给 game DLL） |
| `proto/apis/tappc/m/ws/ws.proto` | 🔶 WS Command enum（TAPSDK_INIT / TAPSDK_AUTHORIZE） |

---

*以上为当前代码全量梳理（主目录：`tap-main/pc`，PC SDK：`tap-main/pc/sdk/tapsdk` + C ABI 头 `tap-main/pc/sdk/tapsdk/loader/taptap_*.h`）。后续如有新增交互点请同步更新本文档。*
