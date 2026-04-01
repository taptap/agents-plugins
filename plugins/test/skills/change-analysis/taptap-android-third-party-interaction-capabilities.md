# TapTap Android 主站 - 三方应用交互能力梳理

梳理范围：主站端（taptap-android/cn/app）与外部三方应用之间的全量交互能力及代码位置。

更新时间：2026-03-31

---

## 一、SDK 调用 TapTap 主站的能力模块

> SDK 侧（tap-license / tap-share / tap-achievement / tap-review / tap-rep / tap-relation 等模块）调用 TapTap 主站客户端时，会经过以下主站代码块。**MR 改动这些文件时需特别注意对外部 SDK 接入方的兼容性影响。**
>
> 参考：[TapTap SDK Android 三方 - 调用 TapTap 主站交互能力梳理](taptap-sdk-android-to-main-app-calls.md)

### 1.1 登录授权（XDSDK → TapTapSdkActivity）

**SDK 调用入口**：XDSDK `startActivityForResult(action = com.taptap.sdk.action)`

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| 入口 Activity | `com.play.taptap.sdk.SdkDelegateActivity` |
| 实际处理 | `com.play.taptap.sdk.TapTapSdkActivity` / `TapTapSdkActivityTransparent` |
| 核心基类 | `infra/dispatch/first-party-login/ui/.../sdk/BaseTapAccountSdkActivity.kt` |
| Manifest action | `com.taptap.sdk.action`（exported=true） |
| 代码路径 | `feat/startup/startup-core/src/main/java/com/play/taptap/sdk/` |

流程：游戏发起 `startActivityForResult`，`SdkDelegateActivity` 校验隐私协议 → `TapTapSdkActivity` 校验调用方包名+签名 → `openLogin(LoginMode.Sdk)` → 结果通过 `setResult` + `LoginResponse Bundle` 回传。

特殊场景：
- 沙盒内游戏：通过 `SandboxExportService.getCallingActivity()` 获取调用方
- 云玩内游戏：包名/签名通过 Intent extra 传入（`EXTRA_CLOUD_GAME_PACKAGE_NAME` / `EXTRA_CLOUD_GAME_PACKAGE_SIGN`）
- SDK 版本兼容：`TapSDKCompat` 处理 3.x 以下版本横竖屏兼容逻辑

**MR 风险**：`com.taptap.sdk.action` Action 字符串或返回 `LoginResponse Bundle` 字段结构变更 → SDK 登录流程断链

---

### 1.2 购买授权查询（InAppBillingService AIDL）

**SDK 调用入口**：`CNIabService` / `GlobalIabService`（tap-license）→ `bindService(com.play.taptap.billing.InAppBillingService.BIND)`

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| Service 类 | `com.play.taptap.service.InAppBillingService` |
| AIDL 接口 | `feat/biz/biz-api/.../IInAppBillingService.aidl` |
| 回调接口 | `feat/biz/biz-api/.../ICallback.aidl` |
| Manifest action | `com.play.taptap.billing.InAppBillingService.BIND`（exported=true） |
| 代码路径 | `feat/biz/biz-api/src/main/java/com/play/taptap/service/` |

AIDL 接口方法：`isBillingSupported` / `isAppLicensed` / `getSkuDetails` / `getBuyIntent` / `getPurchases` / `consumePurchase` / `getBuyIntentToReplaceSkus`

**MR 风险**：⚠️ 高 — AIDL 方法签名或 Bundle key 变更 → 所有接入正版验证的游戏立即失效

---

### 1.3 授权检查兜底（CheckLicenseAct）

**SDK 调用入口**：`TapLicenseFragment`（tap-license）→ `startActivityForResult(com.play.taptap.billing.CheckLicenseAct)`

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| Activity 类 | `com.taptap.game.export.pay.CheckLicenseAct` |
| Manifest action | `com.play.taptap.billing.CheckLicenseAct`（exported=true） |
| 接口 | `feat/biz/biz-api/.../ICheckLicenseAct.kt` |
| Proxy 实现 | `feat/game/game-pay/.../CheckLicenseActProxy.kt` |
| 代码路径 | `feat/biz/biz-api/src/main/java/com/taptap/game/export/pay/` |

Service 方式被部分厂商屏蔽时的兜底方案，透明 Activity 无感操作。

**MR 风险**：⚠️ 高 — Action 变更或 `onActivityResult` 返回结构变更 → 正版验证兜底通道失效

---

### 1.4 DLC 内购（TapTapDLCAct）

**SDK 调用入口**：`TapLicenseFragment.purchaseDLC()`（tap-license）→ `startActivityForResult(com.play.taptap.billing.InAppBillingAct)`

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| Activity 类 | `com.taptap.game.export.pay.TapTapDLCAct` |
| Manifest action | `com.play.taptap.billing.InAppBillingAct`（exported=true） |
| 接口 | `feat/biz/biz-api/.../ITapTapDLCAct.kt` |
| Proxy 实现 | `feat/game/game-pay/.../TapTapDLCActProxy.kt` |
| 代码路径 | `feat/biz/biz-api/src/main/java/com/taptap/game/export/pay/` |

支持 `testMode`，Extra 参数：`cmd` / `pkg` / `sku` / `price` / `title` / `description`

**MR 风险**：⚠️ 高 — Extra key 变更或 `resultCode` 结构变更 → DLC 购买流程断链

---

### 1.5 Scheme / DeepLink 路由（SchemePath）

**SDK 调用入口**（多模块）：

| SDK 模块 | 调用方式 | 目标 Path |
|---------|---------|----------|
| `TapAchievementInternal`（tap-achievement） | `startActivity(taptap://taptap.com/<achievement_uri>)` | `/game_core/achievement/list` |
| `TapReviewInternal`（tap-review） | `startActivity(<review_uri>?tapsdk_cross_app_code=...)` | `/review` |
| `TapRepInternal`（tap-rep） | `startActivity(<rep_uri>)` | 服务端下发 |
| `SysExt.goTapTap()` / `goGame()`（tap-relation / tap-relation-lite） | `startActivity(<goTapUri>)` | `/app` 等 |
| `CNIabService.openTapTap()`（tap-license 正版验证） | `startActivity(taptap://taptap.com/app?identifier={pkg}&license=yes)` | `/app` |

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| 路由文件 | `common/base-service/data/.../router/path/SchemePath.kt` |
| 格式 | `taptap://taptap.com/<path>`，共 100+ 路由 |
| 关键 Path | `/app`、`/review`、`/game_core/achievement/list`、`/tap_pay_inner` 等 |

**MR 风险**：⚠️ 高 — 删除或重命名现有 path → 对应 SDK 模块的端内跳转全部失效；**SchemePath 已上线路由不可变动**

---

### 1.6 图片分享接收（PushInvokerAct）

**SDK 调用入口**：`TapTapShare.share()`（tap-share）→ `ACTION_SEND_MULTIPLE`，`mimeType=image/*` → 系统分享面板选择 TapTap

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| 接收 Activity | `com.taptap.other.basic.impl.ui.PushInvokerAct` |
| Manifest action | `android.intent.action.SEND` / `android.intent.action.SEND_MULTIPLE`（mimeType=image/*） |
| 代码路径 | `feat/other/export-bis/impl/src/main/java/com/taptap/other/basic/impl/ui/PushInvokerAct.kt` |
| Manifest | `feat/other/export-bis/impl/src/main/AndroidManifest.xml` |

流程：外部应用分享图片 → 系统分享面板选择 TapTap → `PushInvokerAct` 接收 → 解析图片 URI（需 `FLAG_GRANT_READ_URI_PERMISSION`）→ 跳转端内发帖编辑器

**MR 风险**：⚠️ 高 — 移除 Manifest `intent-filter` 声明或 URI 解析逻辑变更 → tap-share 分享功能失效

---

### 1.7 合规认证 & 防沉迷

#### 1.7.1 现行方案（TapSDK 2.x / 3.x / 4.x）

**SDK 调用入口**：TapSDK 登录流程完成后，主站自动触发实名认证页面（通过 `SdkWebFragment` 内嵌 WebView 承接）

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| 承接 Fragment | `infra/dispatch/first-party-login/ui/.../login/sdk/SdkWebFragment.kt`（926 行） |
| 触发时机 | SDK 登录流程中，主站检测用户需要实名认证时弹出 |
| WebView 目标 | 实名认证 H5 页面（URL 由服务端下发） |
| 回调方式 | WebView JSBridge 通知主站认证结果，主站更新用户状态后继续登录流程 |
| Manifest action | 无独立 exported Action，内嵌于登录 Activity 流程中 |
| 代码路径 | `infra/dispatch/first-party-login/ui/src/main/java/com/taptap/common/account/ui/login/sdk/SdkWebFragment.kt` |

关键方法：
- `onPageFinished()`：页面加载完成回调
- `evaluateJavascript()`：主站向 WebView 注入用户信息
- `handleJsMessage()`：接收 WebView 回传的认证结果
- `onCertifySuccess()`：认证成功后继续登录流程

**MR 风险**：🔶 中 — SdkWebFragment 与认证 H5 的 JS 协议变更会导致认证流程中断；URL scheme 或 JSBridge 消息格式变更需同步 H5 侧

#### 1.7.2 古早版本（已废弃，仅存代码兼容）

**SDK 调用入口**：老版本 TapSDK 通过 `bindService(com.play.taptap.AntiAddictionService.BIND)` 或 `startActivity(com.play.taptap.AntiAddiction.Action)`

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| Service 类 | `com.taptap.user.user.export.bis.core.anti.AntiAddictionService` |
| Service action | `com.play.taptap.AntiAddictionService.BIND`（exported=true，**不可删**） |
| AIDL 接口 | `feat/user/export-bis/.../IAntiAddictionInterface.aidl` — `getUserAntiAddictionInfo(callback)` |
| Activity | `com.taptap.user.user.export.bis.core.anti.AntiAddictionAct` |
| Activity action | `com.play.taptap.AntiAddiction.Action`（exported=true） |
| 代码路径 | `feat/user/export-bis/src/main/java/com/taptap/user/user/export/bis/core/anti/` |

**MR 风险**：⚠️ 高 — 当前 SDK 版本已不使用，但老版本仍可能调用；`AntiAddictionService` 及其 Manifest action **不可删除、不可修改 exported 声明**

---

### 1.8 SDK 初始化能力（TapSDKDroplet）

**SDK 调用入口**：游戏集成 TapSDK 后，SDK 在初始化阶段通过 `TapSDKDropletService` 调用主站进程，主站向 SDK 提供端内能力初始化

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| 实现类 | `feat/startup/startup-tapsdkdroplet/src/main/java/com/taptap/startup/tapsdkdroplet/TapSDKServiceImpl.kt` |
| 代码路径 | `feat/startup/startup-tapsdkdroplet/src/main/java/com/taptap/startup/tapsdkdroplet/` |

端内向 SDK 提供的初始化能力：

| 方法 | 说明 | 影响 |
|------|------|------|
| `initTapKit()` | TapKit 初始化（clientId + clientSecret） | SDK 基础能力依赖 |
| `initOpenLog()` | TapTapOpenlogSdk 开放日志初始化 | SDK 日志上报 |
| `initGid()` | TapSdkGid 设备 GID / TDID 生成与回调 | 设备唯一标识 |

**MR 风险**：🔶 中 — 三个 init 方法的参数类型或回调签名变更 → SDK 初始化失败，影响所有依赖 TapSDK 的游戏

---

### MR 速查：SDK 高风险文件

| 文件 | 所属模块 | 影响 |
|------|---------|------|
| `feat/biz/biz-api/.../IInAppBillingService.aidl` | 1.2 | ⚠️ 正版验证/购买 AIDL 接口，方法签名不可变 |
| `feat/biz/biz-api/.../ICallback.aidl` | 1.2 | ⚠️ AIDL 异步回调接口，不可变 |
| `feat/biz/biz-api/.../InAppBillingService.kt` | 1.2 | ⚠️ Billing Service 主体，Manifest action 不可变 |
| `feat/game/game-pay/.../IabAppLicenseManager.kt` | 1.2/1.3 | ⚠️ 正版验证查询核心实现，CheckLicense/DLC 均依赖 |
| `feat/biz/biz-api/.../CheckLicenseAct.kt` | 1.3 | ⚠️ 正版验证兜底 Activity，Action + 返回结构不可变 |
| `feat/biz/biz-api/.../TapTapDLCAct.kt` | 1.4 | ⚠️ DLC 内购入口，Extra key + resultCode 不可变 |
| `feat/game/game-pay/.../TapTapDLCCheckInitHelper.kt` | 1.4 | ⚠️ DLC 初始化辅助，影响 DLC 购买前置流程 |
| `common/base-service/.../SchemePath.kt`（删改现有 path） | 1.5 | ⚠️ 已上线路由不可删改，影响成就/评价/REP/关系链/正版验证 |
| `feat/other/export-bis/impl/.../PushInvokerAct.kt` | 1.6 | ⚠️ 图片分享接收，Manifest filter 不可删 |
| `feat/user/export-bis/.../AntiAddictionService.java` | 1.7 | ⚠️ 老版本 SDK 防沉迷 Service，不可删、exported 不可改 |
| `feat/user/export-bis/.../IAntiAddictionInterface.aidl` | 1.7 | ⚠️ 老版本防沉迷 AIDL 接口，不可删 |
| `feat/user/export-bis/.../IAntiAddictionInfoCallback.aidl` | 1.7 | ⚠️ 老版本防沉迷 AIDL 回调，不可删 |
| `feat/startup/startup-core/.../TapTapSdkActivity.kt` | 1.1 | 🔶 登录授权接口层，Action 字符串变更影响 SDK |
| `infra/dispatch/.../BaseTapAccountSdkActivity.kt` | 1.1 | 🔶 登录授权核心基类，返回 Bundle 结构变更影响 SDK |
| `infra/dispatch/.../SdkWebFragment.kt` | 1.7 | 🔶 合规认证 WebView，JSBridge 协议变更需同步 H5 |
| `feat/startup/tapsdkdroplet/.../TapSDKServiceImpl.kt` | 1.8 | 🔶 SDK 初始化能力，init 方法签名变更影响所有接入游戏 |

---

## 二、内嵌 WebView JS Bridge

> 非 SDK 调用路径，为主站内嵌 WebView 对内部 H5 页面暴露的能力。

### 2.1 主站 WebView JSBridge（11 个 Handler）

`window.TapTapAPI(action, params)` 统一入口，每个 action 受 `WebPermissionRule` 管控。

代码路径：`feat/other/tap-basic/impl/src/main/java/com/taptap/other/basic/impl/web/jsb/`

| Handler | 主要能力 |
|---------|---------|
| `TapTapApiHandler` | 统一入口分发（70 行） |
| `AuthHandler` | 登录态/token（161 行） |
| `SystemInfoHandler` | 设备/系统信息（215 行） |
| `UiControlHandler` | UI 控制（222 行） |
| `ContentHandler` | 内容相关（193 行） |
| `GameHandler` | 游戏相关（108 行） |
| `BusinessHandler` | 业务逻辑（129 行） |
| `ShareHandler` | 分享（225 行） |
| `MediaHandler` | 媒体（104 行） |
| `AppManagementHandler` | 应用管理（86 行） |
| `CloudGameMessageHandler` | 云游戏消息（176 行） |
| `HookThirdWebHandler` | 三方 WebView Hook（180 行） |

权限控制：`feat/other/tap-basic/impl/.../web/permission/WebPermissionRule.kt`

### 2.2 悬浮球菜单 WebView JSBridge

代码路径：`feat/game/game-common/src/main/java/com/taptap/game/common/floatball/menu/web/FloatWebJsBridge.kt`（565 行）

支持 `login` / `getLoginCertificate` / `tapLog` 等 action。

### 2.3 三方 WebView 注入（InjectJsWebView）

代码路径：`feat/other/tap-basic/impl/.../web/InjectJsWebView.kt`（149 行）

向三方 WebView 注入自定义 JS，可配置 `jsbObjName` / `callbackMethodName` / `userAgent` / `js`。

---

## 三、沙盒进程 AIDL 通信

> 主站与沙盒进程之间的 IPC 通道，非外部 SDK 调用路径。

### 3.1 沙盒 → 主站（ISandboxCallTapService）

沙盒内游戏调用主站进程的账号检测、防沉迷、路由跳转等能力。

| 项目 | 说明 |
|------|------|
| AIDL 接口 | `feat/biz/biz-api/src/main/.../ISandboxCallTapService.aidl`（1-186 行） |
| 实现类 | `feat/game/game-sandbox/impl/.../SandboxCallTapServiceImpl.kt`（1473 行） |

### 3.2 主站 → 沙盒（ITapService）

主站向沙盒同步用户信息、游戏信息、设备 ID 等。

| 项目 | 说明 |
|------|------|
| AIDL 接口 | `feat/biz/biz-api/src/main/.../ITapService.aidl`（1-90 行） |
| 实现类 | `feat/game/game-sandbox/impl/.../VTapService.kt`（155 行） |

主要方法：`setUserInfo` / `setGameInfo` / `setDeviceId` / `setUserPerfConfig` / `notifyFlush` / `setCraftEnginesPackageNames`

---

## 四、推送唤起

| 通道 | 说明 |
|------|------|
| 在线通道 | 通知栏点击直接走端内 Scheme/DeepLink 路由（见第一章 1.5） |
| 离线 - 阿里推送 | 系统唤起 `com.taptap.push.TapAliyunPopupPushActivity` 中转，解析参数后走 DeepLink |
| 离线 - 个推 | 系统唤起 `com.taptap.push.GeTuiPopupPushActivity` 中转，解析参数后走 DeepLink |

代码路径：`feat/other/export-bis/impl/src/main/AndroidManifest.xml`

---

## 五、桌面小组件唤起

| 类型 | 说明 |
|------|------|
| 桌面文件夹组件 | 通过 `taptap://taptap.deskfolder` 唤起 `DeskFolderPageActivity`，再跳转落地页或打开游戏 |
| 桌面单组件 | 通过标准 Scheme/DeepLink 打开落地页或游戏 |

| 项目 | 说明 |
|------|------|
| Activity | `com.taptap.game.export.deskfolder.DeskFolderPageActivity`（exported=true） |
| 透明中转 | `com.taptap.game.export.deskfolder.DeskFolderTransparentPageActivity` |
| Scheme | `taptap://taptap.deskfolder` |
| 代码路径 | `feat/biz/biz-api/src/main/java/com/taptap/game/export/deskfolder/` |

---

*以上为当前代码全量梳理，后续如有新增交互点请同步更新本文档。*
