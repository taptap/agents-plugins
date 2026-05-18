# 三方交互外部影响评估（Android / iOS / PC）

本模块在 change-analysis 工作流中**按需激活**：仅当待分析 MR 属于 **Android / iOS / PC 主站客户端**项目，
且 diff 命中下方对应平台的高风险文件或交互模块时，才在 `code_change_analysis.md` 追加本章节，
并在 `test_coverage_report.md` 中追加对应的测试访问评估和建议用例。

**平台判定依据**：

| 平台 | 判定信号（仓库/路径包含） |
| ---- | ---- |
| Android | `android`（如 `taptap-android`、`cps/taptap-android`） |
| iOS | `ios`、`tap-main/ios`、`tap-main/ios/cn` |
| PC | `pc`、`tap-main/pc`、`launcher/`、`launcher-intl/`、`emulator-connector/`、`overlay/`、`minigame/`、`sdk/tapsdk/`（PC SDK） |

**参考资料一览**：

| 平台 | 主站侧（命中判断依据） | SDK 侧（兼容性参考） |
| ---- | ---- | ---- |
| Android | [taptap-android-third-party-interaction-capabilities.md](taptap-android-third-party-interaction-capabilities.md) | [taptap-sdk-android-to-main-app-calls.md](taptap-sdk-android-to-main-app-calls.md) |
| iOS | [taptap-ios-third-party-interaction-capabilities.md](taptap-ios-third-party-interaction-capabilities.md) | 主站文档已涵盖 SDK 侧（参 TapSDK-Monorepo/iOS 章节） |
| PC | [taptap-pc-third-party-interaction-capabilities.md](taptap-pc-third-party-interaction-capabilities.md) | 主站文档已涵盖 SDK 侧（PC SDK 与主站同仓库） |

---

## 一、Android 命中判断规则

在阶段 3A（diff 分析）完成后，对照下表检查本次 MR 是否涉及列出的**高风险文件或模块**。
任意一条匹配即视为**命中**，激活本模块后续全流程。

| 匹配维度 | 命中标志 | 参考章节 |
| -------- | -------- | -------- |
| 文件路径包含 `feat/biz/biz-api/.../IInAppBillingService.aidl` 或 `ICallback.aidl` | ⚠️ 正版验证/购买 AIDL | 第 1.2 节 |
| 文件路径包含 `InAppBillingService.kt`（biz-api 模块） | ⚠️ Billing Service | 第 1.2 节 |
| 文件路径包含 `IabAppLicenseManager.kt` | ⚠️ 正版验证核心 | 第 1.2/1.3 节 |
| 文件路径包含 `CheckLicenseAct.kt`（biz-api） | ⚠️ 正版验证兜底 Activity | 第 1.3 节 |
| 文件路径包含 `TapTapDLCAct.kt` 或 `TapTapDLCCheckInitHelper.kt` | ⚠️ DLC 内购 | 第 1.4 节 |
| 文件路径包含 `SchemePath.kt`（base-service）且有**删除/重命名**操作 | ⚠️ Scheme 路由 | 第 1.5 节 |
| 文件路径包含 `PushInvokerAct.kt` 或其 `AndroidManifest.xml` | ⚠️ 图片分享接收 | 第 1.6 节 |
| 文件路径包含 `AntiAddictionService.java` / `IAntiAddictionInterface.aidl` / `IAntiAddictionInfoCallback.aidl` | ⚠️ 防沉迷兼容层 | 第 1.7 节 |
| 文件路径包含 `TapTapSdkActivity.kt` 或 `BaseTapAccountSdkActivity.kt` | 🔶 SDK 登录授权 | 第 1.1 节 |
| 文件路径包含 `SdkWebFragment.kt`（first-party-login） | 🔶 合规认证 WebView | 第 1.7.1 节 |
| 文件路径包含 `TapSDKServiceImpl.kt`（startup-tapsdkdroplet） | 🔶 SDK 初始化能力 | 第 1.8 节 |
| 文件路径包含 `feat/other/tap-basic/.../web/jsb/` 下任意 Handler | 🔶 WebView JSBridge | 第 2.1 节 |
| 文件路径包含 `WebPermissionRule.kt` | 🔶 JSBridge 权限控制 | 第 2.1 节 |
| 文件路径包含 `FloatWebJsBridge.kt` | 🔶 悬浮球 JSBridge | 第 2.2 节 |
| 文件路径包含 `ISandboxCallTapService.aidl` 或 `SandboxCallTapServiceImpl.kt` | 🔶 沙盒 AIDL | 第 3.1 节 |
| 文件路径包含 `ITapService.aidl` 或 `VTapService.kt`（game-sandbox） | 🔶 主站→沙盒 AIDL | 第 3.2 节 |

> 章节号对应 `taptap-android-third-party-interaction-capabilities.md`。**不命中则跳过本模块**。

---

## 二、iOS 命中判断规则

在阶段 3A（diff 分析）完成后，对照下表检查本次 MR 是否涉及列出的**高风险文件或模块**。
任意一条匹配即视为**命中**。iOS 关键区别：所有跨应用调用基于 `UIApplication.shared.open(url:)` +
`application(_:open:options:)` + `application(_:continue:restorationHandler:)`，没有 AIDL/Service IPC。

| 匹配维度 | 命中标志 | 参考章节 |
| -------- | -------- | -------- |
| 文件路径为 `cn/TapTap/Info.plist`（含 `CFBundleURLSchemes` / `LSApplicationQueriesSchemes` / `UIApplicationShortcutItems` / `NSUserActivityTypes` 增删） | ⚠️ URL Scheme / 查询白名单 / Shortcut / Siri | 第 1.1 / 1.4 / 七 / 6.5 节 |
| 文件路径为 `cn/TapTap/TapTap.entitlements`（含 `applinks:` / `com.apple.developer.applesignin` / App Group `group.taptap.share` 增删） | ⚠️ Universal Link / Apple Sign-In / App Group | 第 1.3 / 四 / 九 节 |
| 文件路径包含 `cn/TapTap/Login/viewModel/AuthManager.swift` | ⚠️ SDK OAuth 登录参数协议 | 第 1.2 节 |
| 文件路径包含 `cn/TapTap/Login/VC/TapAuthViewController.swift` | ⚠️ `tapoauth://authorize` 回调拦截 + 授权 WebView JSBridge | 第 1.2 / 5.2 节 |
| 文件路径包含 `cn/TapTap/Login/Social/TapSocialPlatformQQ.swift` 或 `TapSocialPlatformWechat.swift` | ⚠️ QQ/微信 SDK AppID/Universal Link | 第 4 节 |
| 文件路径包含 `cn/TapTap/Launch/Manager/TapLaunchRouterManager.swift` | ⚠️ `universalLinkHosts` / `convertToTapRoute.allowList` / `type=third_share` 识别 / `uri` query 路由 | 第 1.3 / 1.4 / 1.5 / 1.6 节 |
| 文件路径包含 `cn/TapTap/Launch/Manager/TapShareEventsFromGameManager.swift` | ⚠️ 剪贴板 read + NSKeyedUnarchiver 反序列化 | 第 1.3 / 十 节 |
| 文件路径包含 `cn/TapTap/Base/Share/TapThirdEditorShareModel.swift` | ⚠️ NSKeyedArchiver 类名 `TapTap.TapThirdEditorShareModel` + Coding key | 第 1.3 节 |
| 文件路径包含 `cn/TapTap/RouterRegister/TapRouterRegisterManager.swift` | ⚠️ **路由表契约**：`TapPageInsideIdentifier` / `TapPageOutsideIndentifier` 已上线 `rawValue` 不可改 | 第 2 节 |
| 文件路径包含 `cn/TapTap/RouterRegister/TapRouterRedirector.swift` | 🔶 Router 拦截重定向 | 第 2.1 节 |
| 文件路径包含 `cn/TapTap/AppDelegate.swift`（含 `application(_:open:url:)` / `application(_:continue:userActivity:)` 修改） | ⚠️ 四个 handler 优先级顺序 | 第 1.2 / 1.3 / 1.4 / 八 节 |
| 文件路径包含 `cn/TapTap/Base/Payment/TapPaymentManager.swift`（`TapAliPaymentManager`） | ⚠️ Alipay `fromScheme`/`fromUniversalLink` 后台绑定 | 第 4 节 |
| 文件路径包含 `cn/ShareExtension/`（`ShareViewController.swift` / `Info.plist` / `ShareExtension.entitlements`） | ⚠️ App Group + 图片归档 key + `taptap://share-extension` 路由 | 第 6.1 节 |
| 文件路径包含 `cn/PersonalLetter/`（`ShareViewController.swift` / `Info.plist` / `entitlements`） | ⚠️ App Group + 文本 key + `taptap://personalLetterShare` 路由 | 第 6.2 节 |
| 文件路径包含 `cn/NotificationService/` 或 `cn/TapTapWidget/` 或 `cn/TapTapWidgetExtension.entitlements` | ⚠️/🔶 App Group + 推送回执 / Widget Kind 名 / `taptap://app?game_id=...&opener=widget_*` 路由 | 第 6.3 / 6.4 节 |
| 文件路径包含 `cn/TapTap/AppIntents/TapAppIntentsManager.swift` | 🔶 App Intents 类名（Siri Shortcut 绑定） | 第 6.5 节 |
| 文件路径包含 `cn/TapTap/Tools/SchemeTool.swift` | 🔶 `loginSchemePrifixs` 白名单 / `reportApkList` 上报字段 | 第 十一 节 |
| 文件路径包含 `package/TapWebViewController/Sources/TapWebViewController/TapWebViewController+Script.swift` | 🔶 `TapTapAPI` messageHandler name + action 集合 | 第 5.1 节 |
| 文件路径包含 `cn/TapTap/WebView/TapWebViewDelegate.swift` | 🔶 主站业务 JSBridge action 实现 | 第 5.1 节 |
| 文件路径包含 `cn/TapTap/WebView/TapThirdBindWebViewController.swift` 或 `TapGameBindWebView.swift` | ⚠️ `executeJsOnTargetWeb`/`closeTargetWeb`/`getCookie`/`setCookie` 合作伙伴契约 | 第 5.3 节 |
| 文件路径包含 `cn/TapTap/Base/SCEModule/SCEBridge.h` 或 `SCEBridge.m` | ⚠️ **SCE 容器契约**：等价 Android `ISandboxCallTapService.aidl` | 第 3.1 节 |
| 文件路径包含 `cn/TapTap/Base/SCEModule/SCEModule.swift` | ⚠️ SCE 容器生命周期入口 | 第 3.1 节 |
| 文件路径包含 `package/InstantGame/Sources/InstantGameBuildinModules/WXBridge/`（78 个 .swift） | ⚠️ **小游戏容器契约**：兼容微信小游戏子集 API | 第 3.2 节 |
| 文件路径包含 `cn/TapTap/Base/Minigame/TapMinigameIAPAdapter.swift` 或 `TapMinigameRetentionProvider.swift` | ⚠️/🔶 `InstantGameIAPProvider` / `InstantGameRetentionProvider` 协议实现 | 第 3.2 节 |
| 文件路径包含 `cn/TapTap/PlayGame/CloudGame/` | 🔶 云玩 H5 适配 | 第 3.3 节 |

> 章节号对应 `taptap-ios-third-party-interaction-capabilities.md`。**不命中则跳过本模块**。

---

## 三、PC 命中判断规则

在阶段 3A（diff 分析）完成后，对照下表检查本次 MR 是否涉及列出的**高风险文件或模块**。
任意一条匹配即视为**命中**。PC 关键区别：跨进程通信基于 **Windows Named Pipe + gRPC + HTTP + WebSocket**，
SDK 通过 C ABI Loader 调用（无 OS Scheme/AIDL 级契约）。

| 匹配维度 | 命中标志 | 参考章节 |
| -------- | -------- | -------- |
| 文件路径包含 `proto/tapsdk/tapsdk.proto` | ⚠️ SDK gRPC 主入口（EventId / enum / 字段 tag） | 第 1.1 / 1.3 / 1.4 / 1.9 / 1.10 / 1.11 节 |
| 文件路径包含 `proto/tapsdk/cloudsave/`、`proto/tapsdk/achievement/`、`proto/tapsdk/compliance/` 下任意 `.proto` | ⚠️ SDK 子服务 RPC 签名 | 第 1.6 / 1.7 / 1.8 节 |
| 文件路径包含 `proto/apis/clientapi/pcsdk/core/core.proto` | ⚠️ PCSDKCore（SdkInit / RefreshOwnershipTicket / AndroidOwnershipTicket + TYPE_GAME/TYPE_DLC） | 第 1.1 / 1.5 / 3.3 节 |
| 文件路径包含 `proto/minigame/minigame.proto` 或 `proto/minigame/api/api.proto` | ⚠️ 小游戏容器协议 | 第 3.1 节 |
| 文件路径包含 `proto/apis/tappc/launcher/launcher.proto` | ⚠️ Launcher HTTP API（含 HandleSecondInstance — OS scheme 接入点） | 第 2.2 / 1.2 节 |
| 文件路径包含 `proto/apis/tappc/gamemgr/gamemgr.proto` | ⚠️ 游戏管理 14 个 RPC | 第 2.2 / 八 节 |
| 文件路径包含 `proto/apis/tappc/m/tappc.proto` | ⚠️ Composer.Action / Composer.Status 取值 | 第 十一 节 |
| 文件路径包含 `sdk/tapsdk/loader/taptap_api.h` / `taptap_achievement.h` / `taptap_cloudsave.h` / `taptap_compliance.h` / `taptap_onlinegame.h` | ⚠️ **C ABI 头**：48 个 `T_API` 符号 + 枚举 + `T_CALLTYPE` 调用约定 | 第 1.12 节 |
| 文件路径包含 `main/pkg/ipc_name/ipc_name_cn.go` 或 `ipc_name_global.go` | ⚠️ Pipe 名称（4 个常量，CN/Global 必须同步） | 第 2.1 节 |
| 文件路径包含 `main/internal/api/tapsdk_grpc/server.go` | ⚠️ Init 的进程校验 + 四个 handler | 第 1.1 / 1.3 / 1.4 / 1.10 / 1.11 节 |
| 文件路径包含 `main/internal/api/tapsdk_grpc/{cloudsave,achievement,compliance}/server.go` 或 `compliance.go` | ⚠️ 子服务注册 | 第 1.6 / 1.7 / 1.8 节 |
| 文件路径包含 `main/internal/api/tappc_http/server.go`（含 `withVerifyRequestProcess` 修改） | ⚠️ PID 校验是 tappc HTTP 安全契约 | 第 2.3 节 |
| 文件路径包含 `main/internal/api/tappc_http/launcher/launcher.go` | ⚠️ HandleSecondInstance — OS scheme → 路由分发起点 | 第 1.2 / 2.2 节 |
| 文件路径包含 `main/internal/service/tapsdk/tapsdk.go` | ⚠️ SdkInit 落地 | 第 1.1 节 |
| 文件路径包含 `main/internal/service/process_mapping/detector.go` | 🔶 进程绑定校验（沙盒/SCE/模拟器场景） | 第 1.1 节 |
| 文件路径包含 `main/internal/service/android_gamemgr/emulator/connector` | 🔶 PC ↔ emulator-connector 桥接 | 第 3.3 节 |
| 文件路径包含 `launcher/src/shared/config.ts`（`URL_PROTOCOL` / `URL_HOST` / `URL_SCHEME` / `DEFAULT_WEBVIEW_DOMAIN_WHITELIST` 修改） | ⚠️ CN Scheme 拼装 + WebView 域名白名单 | 第 4.1 / 5.4 节 |
| 文件路径包含 `launcher-intl/src/shared/config.ts`（`OAUTH_SCHEME` / `OAUTH_CLIENT_ID` 修改） | ⚠️ Intl OAuth Scheme 绑定 | 第 4.2 节 |
| 文件路径包含 `launcher-intl/src/main/app.ts`（`setAsDefaultProtocolClient` 调用变更） | ⚠️ Intl Scheme OS 注册 | 第 4.2 节 |
| 文件路径包含 `launcher/src/main/app.ts`（`second-instance` handler 修改） | ⚠️ OS scheme 唤起入口 — `handleArgv` 调用 | 第 1.2 / 4.1 节 |
| 文件路径包含 `launcher/src/main/features/app/protocol.ts` | ⚠️ `handleArgv` / `handleSchemeUri` 实现 | 第 4.1 节 |
| 文件路径包含 `launcher/src/shared/features/client-url/scheme-handler.ts` | ⚠️ **路由表契约**：17 个 pathname + native action 入参 schema（CN/Intl 共享） | 第 5 节 |
| 文件路径包含 `launcher/src/shared/router-config.ts` | ⚠️ RouterNames enum + Vue 路由映射 | 第 5 节 |
| 文件路径包含 `launcher/src/preload/shared/tap-tap-api.ts` | ⚠️ TapTapAPI 公开 JS 函数清单（contextBridge 暴露） | 第 6.1 / 6.3 节 |
| 文件路径包含 `launcher/src/main/features/window/taptap-api.ts` | ⚠️ ipcMain handler + TapApiMessageAction 分发 | 第 6.1 / 6.2 节 |
| 文件路径包含 `launcher/src/shared/types/tapapi.ts` | ⚠️ `TapApiAction` / `TapApiMessageAction` 字符串枚举 | 第 6.2 节 |
| 文件路径包含 `launcher/src/main/features/app/taptap.ts`（含 `isSecureDomain` 修改） | ⚠️ JSBridge 准入域名校验 | 第 6.1 / 5.4 节 |
| 文件路径包含 `setup/NSIS_SetupSkin/SetupScripts/TapTap_CN/ui_TapTap_setup.nsh` 或 `TapTap_Intl/ui_TapTap_setup.nsh` | ⚠️ Windows 注册表 `HKCR\taptap` 写入/清理 | 第 4.1 节 |
| 文件路径包含 `minigame/bridge-scripts/entry.taph5a.js` | ⚠️ 小游戏 cross-object 编码协议（`$js_handle`/`$native_handle`/`$$`/`$#`） | 第 3.1 节 |
| 文件路径包含 `emulator-connector/app/src/main/AndroidManifest.xml` | ⚠️ 8 个 exported 组件 + Action 字符串（必须与 Android 主站同步） | 第 3.3 节 |
| 文件路径包含 `emulator-connector/app/src/main/aidl/`（任意 `.aidl` 文件） | ⚠️ 等价 Android 主站 AIDL，方法签名不可改 | 第 3.3 节 |
| 文件路径包含 `overlay/overlay-native/src/ipc/simple_ipc_client.h` 或 `.cpp` | ⚠️ Overlay 注入端 C++ 公开 API（game DLL 已硬编码） | 第 九 节 |
| 文件路径包含 `proto/apis/tappc/m/ws/ws.proto` | 🔶 WebSocket Command enum（TAPSDK_INIT / TAPSDK_AUTHORIZE） | 第 十 节 |

> 章节号对应 `taptap-pc-third-party-interaction-capabilities.md`。**不命中则跳过本模块**。

---

## 激活后操作流程（平台通用）

### 步骤 1：写入 `code_change_analysis.md` 外部影响评估章节

在阶段 4（impact）完成影响面分析后，追加以下章节到 `code_change_analysis.md`：

```markdown
## 八、外部影响评估（{Android | iOS | PC} 三方交互）

> 本章节由 {平台名称} 三方交互命中检测自动激活，分析本次变更对外部 SDK / 游戏接入方的潜在影响。

### 8.1 命中交互模块汇总

| 交互模块 | 命中文件 | 风险等级 | 参考章节 |
| -------- | -------- | -------- | -------- |
| （按命中填写） | ... | ⚠️/🔶 | ... |

### 8.2 逐模块兼容性风险分析

> 对每个命中的交互模块，按以下格式分析：

#### {模块名称}（如：iOS 1.3 SDK 分享回站 / PC 1.1 SDK 启动 & 版本协商 / Android 1.2 购买授权查询）

**变更内容**：
- 简要描述本次 diff 中对该模块的具体改动（引用变更点编号或完整描述）

**影响分析**：
- **向前兼容性**：现有接入该接口的游戏 / SDK 是否仍可正常调用（是 / 否 / 需验证）
- **接口契约变化**：
  - Android：AIDL 方法签名 / Bundle key / Action 字符串 / resultCode / Extra key
  - iOS：URL Scheme / Universal Link host / NSKeyedArchiver 类名 / Coding key / query 参数名 / App Group / messageHandler action
  - PC：proto 字段 tag / EventId / enum 取值 / C ABI 符号名/参数/返回类型 / Named Pipe 名称 / HTTP 路径 / contextBridge 暴露名
- **受影响 SDK 模块**：列出依赖该交互点的 SDK 模块（参考对应平台主站文档）
- **潜在断链场景**：如有变更，描述哪些 SDK 调用路径会断链或异常

**置信度**：[已确认] / [基于 diff] / [推测]

**建议措施**：
- 是否需要 SDK 侧联动发版
- 是否需要灰度验证特定游戏
- 是否有协议冻结要求（如 AIDL 方法签名 / proto tag / C ABI 符号 / NSKeyedArchiver 类名）

### 8.3 综合外部影响等级

| 影响等级 | 判定标准 |
| -------- | -------- |
| 🔴 高    | 任意 ⚠️ 高风险模块发生接口契约变化，可能导致已接入游戏运行时断链 |
| 🟡 中    | 🔶 中风险模块变更，或 ⚠️ 高风险模块仅内部实现调整不涉及接口契约 |
| 🟢 低    | 变更均为内部逻辑，不影响任何对外接口契约 |

**本次综合外部影响等级**：🔴/🟡/🟢（填写结论并说明依据）
```

---

### 步骤 2：追加外部影响测试访问评估到 `test_coverage_report.md`

在阶段 6（generate）的测试用例生成**完成后**，继续追加以下章节：

```markdown
## 八、外部影响测试访问评估（{Android | iOS | PC} 三方交互）

> 本章节随外部影响评估模块激活，提供针对三方交互变更的测试路径和建议用例。

### 8.1 测试访问路径说明

> 仅列出本次**命中的模块行**，未命中的行删除。下表列出各平台典型访问路径，按本次命中模块选择参考。
```

**Android 测试访问路径**（命中模块按需保留行）：

| 命中模块 | 测试访问方式 | 最低验证手段 |
| -------- | ------------ | ------------ |
| 1.1 SDK 登录授权 | 使用集成 TapSDK 的测试游戏执行登录流程 | 能正常返回 LoginResponse Bundle |
| 1.2 InAppBillingService AIDL | 通过 tap-license 测试 Demo 绑定 Service | AIDL 方法调用返回正确结果 |
| 1.3 CheckLicenseAct | 启动 CheckLicenseAct 并检查 onActivityResult | resultCode 和返回结构正确 |
| 1.4 DLC 内购 | 触发 DLC 购买流程 | DLC 内购弹窗正常显示，resultCode 正确 |
| 1.5 Scheme 路由 | 通过 `adb shell am start` 触发对应 Scheme | 能正常跳转到目标页面 |
| 1.6 图片分享 | 从外部 App 发起图片分享，选择 TapTap | 分享成功且发帖编辑器正常打开 |
| 1.7 防沉迷兼容 | 通过老版本 SDK Demo 绑定 AntiAddictionService | 调用 `getUserAntiAddictionInfo` 返回正常 |
| 1.8 SDK 初始化 | 使用 TapSDK Demo 执行完整初始化流程 | TapKit / OpenLog / GID 初始化无报错 |
| 2.1 JSBridge | 打开内嵌 H5 页面调用对应 action | JSBridge 响应正常，权限校验生效 |
| 2.2 悬浮球 JSBridge | 在游戏中打开悬浮球，触发 H5 功能 | `login` / `getLoginCertificate` 等 action 正常 |
| 3.1 沙盒 AIDL | 在沙盒内运行游戏并触发对应能力 | 账号检测 / 防沉迷 / 路由跳转正常 |
| 3.2 主站→沙盒 | 在沙盒游戏运行时触发用户信息同步 | `setUserInfo` / `setGameInfo` 等正常同步 |

**iOS 测试访问路径**（命中模块按需保留行）：

| 命中模块 | 测试访问方式 | 最低验证手段 |
| -------- | ------------ | ------------ |
| 1.1 SDK 检测主站安装 | 集成 SDK 的测试游戏执行 `canOpenURL("tapsdk://")` / `canOpenURL("tapsdk2://")` | 返回 `true`，安装态检测成功 |
| 1.2 SDK OAuth 登录 | 使用集成 TapTapLogin 的测试游戏触发 `tapsdk://login?...` | `TapClientWebAuth.handleOpenUrl` 拦截成功，授权页打开 |
| 1.3 SDK 分享回站 | TapTapShare Demo 调用 `share(_:)`，触发 Universal Link 回站 | `TapShareEventsFromGameManager` 读取剪贴板并打开发帖编辑器 |
| 1.4 SDK 跳转打开 URI | SDK 调用 `TapTapRep.open(openUrl:)` 触发 `taptap://taptap.com/app?game_id=...` | 主站正确路由到对应页面 |
| 1.5 跳转端内成就页 | TapTapAchievement Demo 调用 `showAchievements()` | 成就页正常打开（依赖 `tapsdk://` 探测 + 服务端 URI） |
| 1.6 跳转好友/通知 | TapTapRelation Demo 触发好友页 / 通知页跳转 | 主站路由对应 URI 不 404 |
| 1.7 SDK 内嵌 WebView 检测 | TapTapMoment WebView 内 H5 检查 `HAS_TAPTAP_CLIENT` 注入 | 注入值与 `canOpenURL` 结果一致 |
| 2 路由表 | 通过 `xcrun simctl openurl` 触发已上线 path（如 `taptap://taptap.com/app?game_id=1`） | Router 解析成功，落地目标页 |
| 3.1 SCE Bridge | 用 SCE 测试脚本调用 SCEBridge 暴露方法（login / share / showAchievements 等） | bridge 回调 schema 与签名一致 |
| 3.2 InstantGame WXBridge | 用小游戏 Demo 验证 WXBridge action（登录/分享/IAP/广告） | 微信小游戏子集 API 行为一致 |
| 3.3 CloudGame H5 | 启动云玩游戏并触发对应 H5 JSBridge action | OAuth / 状态同步等行为一致 |
| 4 社交平台登录回调 | 使用 QQ/微信/Apple 完成第三方登录授权后回跳 | TapTap 接收回调 + 完成账号绑定 |
| 5.1 主站 WebView JSBridge | 打开白名单内 H5 页面调用 `window.TapTapAPI(action, params)` | 各 action 行为符合契约，白名单校验生效 |
| 5.3 三方应用绑定 WebView | 触发 `executeJsOnTargetWeb` / `closeTargetWeb` / `getCookie` / `setCookie` | 合作伙伴账号互通逻辑正常 |
| 6.1 ShareExtension | 系统分享面板选 TapTap 分享图片 | App Group 内图片归档成功，主站接收后打开发布器 |
| 6.2 PersonalLetter | 系统分享面板选 TapTap 分享文本/链接 | App Group key 接收成功，主站接收后打开私信 |
| 6.3 NotificationService | 推送下发含 `image_url` 的富推送 | 富推送渲染成功，回执接口被调用 |
| 6.4 TapTapWidget | 桌面添加 Widget 并点击跳转 | Widget Kind 名匹配，路由跳转成功 |
| 6.5 NSUserActivity / App Intents | 在 Siri 触发 `RankIntentIntent` / `TapSearchIntent` 等 | 主站接收 NSUserActivity 并跳转到对应页面 |
| 七 Shortcut | 长按 App 图标触发 search / scan / post / taptapai | 跳转到对应页面 |
| 八 推送唤起 | APNs 推送下发 `userInfo.uri = taptap://...` | 点击通知唤起主站并路由 |
| 九 Universal Link | 通过 Safari 或 Notes 打开 `https://www.taptap.cn/...` | 主站 Universal Link 拦截并跳转 |
| 十 剪贴板 | 触发 SDK 分享后查看剪贴板序列化 | NSKeyedArchiver 类名/Coding key 一致 |
| 十一 LSApplicationQueriesSchemes | SDK Demo 检测 `canOpenURL` 多个三方游戏 scheme | 列表上报准确，登录前缀过滤生效 |

**PC 测试访问路径**（命中模块按需保留行）：

| 命中模块 | 测试访问方式 | 最低验证手段 |
| -------- | ------------ | ------------ |
| 1.1 TapSDK_Init | 用 C++/Unity 测试游戏调用 `TapSDK_Init(errMsg, pubKey)` | 返回 `OK`，`InitResponse` 字段完整（client_id/app_id/openid/ownership_ticket） |
| 1.2 TapSDK_RestartAppIfNecessary | 关闭 Launcher 后直接启动测试游戏 | Loader 自动拉起 `taptap.exe` 并完成 `auto_launch=yes` 流程 |
| 1.3 TapUser_AsyncAuthorize | 测试游戏触发授权，Launcher 弹授权窗 | 接收 `EventId_AuthorizeFinished = 2001` 事件，回调 callback_uri |
| 1.4 TapSDK.Stream / ListenEvent | 测试游戏订阅 `EventId_SystemStateChanged` / `EventId_OwnershipChanged` | 事件触发后 Stream 收到对应消息 |
| 1.5 TapApps_IsOwned / TapDLC_* | 已购买/未购买 DLC 场景下调用 IsOwned + ShowStore | 返回值正确，Store 弹窗或路由打开 |
| 1.6 CloudSave | 测试游戏调用 `TapCloudSave_AsyncList/Create/...` | 6 个 RPC 全部返回正常，对应 EventId 触发 |
| 1.7 Achievement | 测试游戏调用 `TapAchievement_Unlock/Increment` | RPC 调用成功，EventId 7001/7002 触发 |
| 1.8 Compliance | 测试游戏调用 `TapCompliance_AsyncEnsureRealName` 等 | 4 个 RPC 行为符合契约，EventId 8001/8002 触发 |
| 1.9 OnlineGame | 测试游戏调用 18 个 `TapOnlineGame_Async*` | Stream 请求/通知 EventId 区间分配正确 |
| 1.10 Record | 测试游戏触发任意 SDK 调用 | `RecordLog` 字段 `action/args/timestamp` 上报正常 |
| 1.11 HealthCheck / SessionCheck | 旧 Loader 启动后探活 | `Unimplemented` 视为成功；新 Loader 正常返回 |
| 1.12 C ABI 符号 | 用 `dumpbin /exports tapsdk-core.dll`（Windows）或 `nm`（Unix）检查导出符号 | 48 个 `T_API` 符号、名称/参数/调用约定与游戏端硬链接一致 |
| 2.1 Named Pipe | 检查 `\\.\pipe\tappc_cn_tapsdk_grpc` 等 4 个 pipe 监听 | Pipe 名称匹配，连接成功 |
| 2.3 进程身份校验 | 用非游戏进程尝试调用 tappc HTTP / TapSDK gRPC | PID 校验生效（拒绝调用）；HandleSecondInstance 例外通过 |
| 3.1 Minigame Bridge | 启动小游戏并验证 `entry.taph5a.js` cross-object 协议 | `GameCommand.type=stop_game` / `GameLifecycle.status=playing` 生效 |
| 3.2 InstantGames Runtime | 调用 `/instant-games-runtime/get` + `install` | 资源版本下发与安装成功 |
| 3.3 Emulator + connector | 模拟器内运行接入老 Android TapSDK 的游戏 | Action / AIDL / Activity 与 Android 主站一致；`AndroidOwnershipTicket` 返回正确 |
| 4 URL Scheme | 浏览器输入 `taptap://taptap.com/app?game_id=1` 或 `open-taptap-{clientID}://authorize?...` | Launcher 唤起，`second-instance` 事件 + `handleArgv` 处理成功 |
| 5 Scheme 路由表 | 触发 17 个 pathname（含 native action `close-webview` / `confirm_order` / `steam_account_data_bind`） | 路由全部命中且 query 参数解析正确 |
| 5.4 域名白名单 | H5 在 `secure_domains` 外尝试调用 `window.TapTapAPI` | 拒绝，白名单内允许 |
| 6 Electron JSBridge | 在 WebView 内调用 `window.TapTapAPI.login/getLoginCertificate/openBrowser/openApp` 等 | IPC 通道 `tapapi:get` 工作正常，action 字符串匹配 |
| 七 推送唤起 | 触发本地通知（payload 含 `uri = taptap://...`） | 点击后唤起对应 Scheme 路由 |
| 八 桌面快捷方式 | 调用 `Gamemgr.AddDesktopShortcut` | 桌面生成快捷方式，启动后能正常拉起游戏 |
| 九 Overlay | 启动支持 Overlay 的 D3D11 游戏，按 F12 显示 | 注入成功，DXGI Shared Texture 传输 + Named Pipe 控制通道工作正常 |
| 十 WebSocket | 触发 `wspb.Command_TAPSDK_AUTHORIZE` | Launcher Renderer 收到命令并弹授权窗 |
| 十一 Composer | 触发游戏下载 / 校验 / 安装 / 卸载 | `Composer.Action` / `Composer.Status` 枚举正确 |

```markdown
### 8.2 建议测试用例

> 为每个命中模块生成不少于 1 条关键路径测试用例和 1 条边界/异常测试用例。
> 同时将这些用例写入 `change_supplementary_cases.json`（格式同 [CONVENTIONS.md 用例 JSON 格式](../commons/CONVENTIONS.md#用例-json-格式)，
> 禁止包含 tags 字段，标签由后端自动赋值）。

#### {命中模块名称} — 关键路径

- **优先级**：P0（⚠️ 高风险模块）/ P1（🔶 中风险模块）
- **前置条件**：
  - Android：使用集成对应 TapSDK 模块的测试游戏；主站安装包为本次变更版本
  - iOS：测试 iPhone / iPad 安装本次变更版本的 TapTap；测试游戏集成对应 SDK 模块
  - PC：Windows 测试机安装本次 Launcher 版本；测试游戏链接对应 Loader 版本（C++/Unity）
- **步骤**：
  1. 操作：{发起调用 — 见上方对应平台的「测试访问方式」}
     预期结果：{正常返回 / 跳转成功 / 接口响应正确}
  2. 操作：验证接口契约关键字段（参 8.2 节「接口契约变化」）
     预期结果：字段值符合预期，未发生结构性变更

#### {命中模块名称} — 兼容性边界

- **优先级**：P1
- **前置条件**：
  - Android：使用老版本 SDK（明确版本号）的测试游戏
  - iOS：使用老版本 SDK Demo（明确版本号）/ 老版本 TapTap 主站验证 SDK 向后兼容
  - PC：使用老版本 Loader / 老版本游戏验证 ABI 向后兼容（关键 `TapSDK_Init_Result` / `TapSDK_Result` enum 取值）
- **步骤**：
  1. 操作：以老版本方式发起调用
     预期结果：主站能正常响应，不因新版本变更导致老版本断链

### 8.3 回归范围建议

基于外部影响等级，给出回归优先级建议：

- **🔴 高**：上线前必须完成全量外部影响路径验证，建议联系 SDK 侧协同测试
- **🟡 中**：抽取主路径用例（P0/P1）验证，重点关注命中模块的接口契约
- **🟢 低**：随正常回归覆盖，无需单独拉通 SDK 侧验证
```

---

## 与主工作流的衔接说明

| 工作流阶段 | 本模块介入点 | 操作 |
| ---------- | ------------ | ---- |
| 阶段 3A：diff 分析 | MR 属于 Android / iOS / PC 项目时，完成文件分类后执行命中检测 | 对照对应平台的「命中判断规则」标记命中项，记录到 `change_checklist.md` |
| 阶段 4：impact | 追加 `code_change_analysis.md` 第八章 | 按「步骤 1」模板填写逐模块分析（章节标题写明平台） |
| 阶段 6：generate | 追加 `test_coverage_report.md` 第八章 | 按「步骤 2」模板填写，选用对应平台的测试访问路径表，并将新增用例同步写入 `change_supplementary_cases.json` |
| 阶段 7：output | `change_analysis.json` 的 `key_findings` 和 `action_items` 中体现外部影响条目 | 命中 ⚠️ 级别时补充外部影响高风险发现 |

> **不命中时**：上述所有介入点均跳过，不新增任何章节，不影响主工作流其他内容。

> **多平台 MR**：极少数 MR 跨多个平台目录（如同时改 Android 和 PC 的 emulator-connector）— 此时各平台独立执行命中检测，命中后第八章按平台分小节追加（8A / 8B / 8C），互不影响。
