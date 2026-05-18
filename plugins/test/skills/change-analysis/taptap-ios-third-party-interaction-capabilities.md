# TapTap iOS 主站 - 三方应用交互能力梳理

梳理范围：tap-main/ios/cn（TapTap CN 主站 iOS 客户端）与外部三方应用之间的全量交互能力及代码位置。

参考的 SDK 仓库：`/Users/taptap/StudioProjects/github/TapSDK-Monorepo/iOS/TapTapSDK`（TapTapLogin / TapTapShare / TapTapRep / TapTapAchievement / TapTapRelation / TapTapMoment / TapTapLeaderboard 等）。

更新时间：2026-05-18

---

## 一、SDK 调用 TapTap 主站的能力模块

> SDK 侧（TapTapLogin / TapTapShare / TapTapAchievement / TapTapRep / TapTapRelation / TapTapRelationLite 等）调用 TapTap iOS 主站时，通过 URL Scheme + 剪贴板 + Universal Link 三种通道传递数据。**MR 改动这些文件时需特别注意对外部 SDK 接入方的兼容性影响。**
>
> iOS 与 Android 的关键区别：iOS 没有 AIDL/Service IPC，所有跨应用调用都基于 `UIApplication.shared.open(url:)` + `application(_:open:options:)` + `application(_:continue:restorationHandler:)`。

### 1.1 SDK 检测 TapTap 是否安装（tapsdk2 / tapsdk）

**SDK 调用入口**：

| SDK 模块 | 检测方式 |
|---------|---------|
| `TapTapShare` / `TapTapRep` | `canOpenURL("taptap://")` |
| `TapTapAchievement` / `TapTapRelation` / `TapTapRelationLite` | `canOpenURL("tapsdk://")`（CN）或 `canOpenURL("tapiosdk://")`（海外） |

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| Info.plist 声明 | `CFBundleURLSchemes`: `tapsdk`、`tapsdk2`（CFBundleURLName="ForSdkAppQueryTap" 专用于 canOpenURL 探测）、`taptap`、`taptaplane2/3/4`（备份）、`tencent101528186`（QQ 登录回调）、`wx69c85f43cdf28209`（微信登录回调） |
| 代码路径 | `cn/TapTap/Info.plist`（1-69 行） |

> **设计说明**：`tapsdk2` 是为绕过 iOS 14 之后 `LSApplicationQueriesSchemes` 50 个上限专门保留的探测 Scheme。SDK 通过 `canOpenURL("tapsdk2://")` 反向判断 TapTap 是否安装而不占用 `LSApplicationQueriesSchemes` 配额（SDK 自身仍需在游戏侧 Info.plist 中声明）。

**MR 风险**：⚠️ 高 — `tapsdk` / `tapsdk2` / `tapiosdk` / `taptap` 中的任意一个 Scheme 被删除 → SDK 安装态检测全部返回 false，触发 fallback WebView/浏览器路径

---

### 1.2 SDK OAuth 登录授权（TapClientWebAuth）

**SDK 调用入口**：当前主流的 `TapTapLogin` SDK 是 **SDK 内嵌 WKWebView** 直接打开 `accounts.taptap.cn/authorize`（见 `TapTapSDK-Monorepo/iOS/TapTapSDK/TapTapLogin/Private/LoginWebView.swift:148`），登录结果通过游戏自己的 `tt<clientID>://login` Scheme 回调，**不经过 TapTap 客户端**。

老版本／部分场景仍走「调起 TapTap 客户端授权」路径：`UIApplication.shared.open("tapsdk://login?client_id=...&response_type=...&state=...&code_challenge=...&...")`

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| 入口判定 | `TapClientWebAuth.shouldHandle(url:)`：`scheme ∈ {"tapsdk","tapiosdk"} && host == "login"` |
| 入口分发 | `AppDelegate.application(_:open:options:)`：`TapClientWebAuth.handleOpenUrl(url:)` 优先级最高 |
| 授权页 VC | `TapAuthViewController`（embeds WKWebView 加载 `https://accounts.taptap.cn/authorize`） |
| 授权管理 | `AuthManager`（解析 client_id / version / scope / state / code_challenge / response_type / extra / track_info 等参数） |
| OAuth 回调 | 服务端跳转到 `tapoauth://authorize?code=...&state=...` → `TapAuthViewController.webView(_:decidePolicyFor:)` 拦截 |
| 代码路径 | `cn/TapTap/Login/viewModel/AuthManager.swift`（499 行） / `cn/TapTap/Login/VC/TapAuthViewController.swift`（522+ 行） |

关键 query 参数：`client_id` / `version` / `permissions`（scope）/ `state` / `bundle_id` / `response_type` / `login_version` / `code_challenge` / `code_challenge_method` / `orientation` / `info` / `extra` / `track_info`

**MR 风险**：⚠️ 高
- `shouldHandle(url:)` 的 scheme / host 判定不可改动
- `AuthManager` 解析的 query key 名称不可改 — 是 SDK 与主站的契约
- `tapoauth://authorize` callback 拦截逻辑不可删除
- `AppDelegate.application(_:open:url:)` 中四个 handler 的调用顺序需保持

---

### 1.3 SDK 分享回站（TapTapShare）

**SDK 调用入口**：`TapTapShare.share(_ obj: TapTapShareObj)`（`TapTapSDK-Monorepo/iOS/TapTapSDK/TapTapShare/Public/TapTapShare.swift:30`）

实现流程（SDK 侧）：
1. `NSKeyedArchiver.setClassName("TapTap.TapThirdEditorShareModel", for: TapTapShareObj.self)`
2. 归档对象 → `UIPasteboard.general.setItems([["data": data]])`
3. `UIApplication.shared.open(shareUrl)` — `shareUrl` 由服务端配置（`ios_rep_share_url.browser`，是 `https://www.taptap.cn/...?type=third_share&...` 的 Universal Link）

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| Universal Link 入口 | `AppDelegate.application(_:continue:restorationHandler:)` → `TapLaunchRouterManager.handleUniversalLink(webpageURL:isLaunch:)` |
| 识别条件 | `host ∈ universalLinkHosts && query["type"] == "third_share"` |
| 转发到管理器 | `TapShareEventsFromGameManager.markShareEventFromGame(queryItems:)` |
| 应用激活后处理 | `TapShareEventsFromGameManager.didBecomeActive` → 读取剪贴板 |
| 反序列化模型 | `NSKeyedUnarchiver.unarchivedObject(ofClasses: [TapThirdEditorShareModel.self, ...])` |
| 数据模型 | `TapThirdEditorShareModel`：`appId / title / contents / groupLabelId / hashtagIds / footerImages` |
| 完成处理 | `TapEditorManger.showEditorSheet(editorType: [.moment(dict)])` |
| Universal Link 白名单 | `www.taptap.com`、`d.taptap.com`、`www.taptap.cn`、`d.taptap.cn`、`dispatch.taptap.cn`、`dispatch.taptap.com`（DEBUG 多 `dispatch-beta.xdrnd.cn`） |
| Associated Domains | `applinks:www.taptap.com / d.taptap.com / www.taptap.cn / d.taptap.cn / dispatch.taptap.cn / dispatch.taptap.com`（`cn/TapTap/TapTap.entitlements`） |
| App Group | `group.taptap.share`（剪贴板回执 result 存储） |
| 代码路径 | `cn/TapTap/Launch/Manager/TapLaunchRouterManager.swift`（256 行） / `cn/TapTap/Launch/Manager/TapShareEventsFromGameManager.swift`（139 行） / `cn/TapTap/Base/Share/TapThirdEditorShareModel.swift`（43 行） |

数据契约（剪贴板 NSKeyedArchiver）：
- 类名：`TapTap.TapThirdEditorShareModel`（SDK 与主站都注册此名称）
- Coding keys：`appId` / `title` / `contents` / `groupLabelId` / `hashtagIds` / `footerImages`
- 回写结果：剪贴板 `{"data": JSON{"result": 0/-2}}`（SDK 侧通过 `TapApplicationLifeCycleListner` 监听）

**MR 风险**：⚠️ 高
- `TapThirdEditorShareModel` 类名（`TapTap.TapThirdEditorShareModel`）和 Coding key 不可改 — 改动 → SDK 端的 `NSKeyedArchiver.setClassName(...)` 失配，分享数据无法反序列化
- Universal Link 白名单 host 不可删 — 影响 SDK fallback `shareUrl` 接收
- `query["type"] == "third_share"` 识别条件不可改
- `entitlements` 中 `applinks:` 五个域名不可删
- App Group `group.taptap.share` 不可改 — 牵连 ShareExtension/Widget/NotificationService

---

### 1.4 SDK 跳转打开 URI（TapTapRep）

**SDK 调用入口**：`TapTapRep.open(openUrl: String, completion:)`（`TapTapSDK-Monorepo/iOS/TapTapSDK/TapTapRep/Public/TapTapRep.swift:42`）

实现：SDK 内部 `TapTapRepInternal.shared.open(openUrl:completion:)` 调用 `UIApplication.shared.open()`，`openUrl` 由游戏方传入或由 SDK 内部根据服务端配置拼接，通常为 `https://www.taptap.cn/...` 的 Universal Link 或 `taptap://...` Scheme。

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| Scheme 入口 | `AppDelegate.application(_:open:url:options:)` → `TapLaunchRouterManager.handleOpen(url:isPush:false)` |
| Universal Link 入口 | `AppDelegate.application(_:continue:userActivity:)` → `TapLaunchRouterManager.handleUniversalLink` |
| 路由格式转换 | `TapLaunchRouterManager.convertToTapRoute(url:)` — 非 `[taptap,tapsdk,tapsdk2,taptaplane2/3/4]` 白名单的两段 path 自动转 `taptap://taptap.cn/{module}?{module}_id={id}` |
| 实际打开 | `Router.push(url.absoluteString, params:)`（来自 TapRouter SPM 包） |
| 路由注册（taptap://taptap.com/:module） | `AppDelegate.setupRouter()`（517-580 行） |
| H5 dispatch 跳转 | `https://d.taptap.com/tapiosnow/dispatch?uri=...` → 自动拼成 `taptap://taptap.com{uri}` |
| 代码路径 | `cn/TapTap/AppDelegate.swift`（517-580）/ `cn/TapTap/Launch/Manager/TapLaunchRouterManager.swift`（37-165） / `cn/TapTap/RouterRegister/TapRouterRegisterManager.swift` |

**MR 风险**：⚠️ 高
- `allowList` `["taptap", "tapsdk", "tapsdk2", "taptaplane2", "taptaplane3", "taptaplane4"]` 不可删元素 — SDK / iOS 商店分发的备用 Scheme 都依赖
- `taptap://taptap.com/:module` 路由格式不可改 — 是 SDK + Web 唤端共用的契约
- `https://d.taptap.com/tapiosnow/dispatch` 域名规则不可改 — 是 SDK + 服务端 dispatch 共用入口

---

### 1.5 SDK 跳转端内成就页（TapTapAchievement）

**SDK 调用入口**：`TapAchievementManager.showAchievements()`（`TapTapSDK-Monorepo/iOS/TapTapSDK/TapTapAchievement/Private/TapAchievementManager.swift:150`）

实现：
1. 通过 `TapSDKMediator.triggerEvent("TapTapSDK/GetClientSettingsPath", ...)` 从服务端 `ClientSetting.urls.achievement_my_list_url.uri` 取得 client 跳转 URI
2. 如果 `canOpenURL("tapsdk://")` 为 true → `UIApplication.shared.open(URL(string: clientUri))`
3. 否则 fallback 到 SDK 内嵌 WebView 打开 `getGatekeeperHost()/achievement/me?client_id=...`

**主站承接代码**：

| 项目 | 说明 |
|------|------|
| 入口 | `AppDelegate.application(_:open:url:options:)` → `TapLaunchRouterManager.handleOpen(url:isPush:)` |
| 路由实现 | TapRouter 注册的成就页路由（来自服务端 `achievement_my_list_url.uri` 字段，主站需保证对应路由可用） |
| 关键依赖 | `tapsdk` Scheme 必须在 Info.plist；`Router` 必须能解析服务端返回的 URI |

**MR 风险**：🔶 中 — clientUri 由服务端下发，前端只需确保 Router 能处理；删除任意成就相关路由 → SDK 跳转后路由 404；`tapsdk://` 探测 scheme 不可删

---

### 1.6 SDK 跳转好友/通知页面（TapTapRelation / TapTapRelationLite）

**SDK 调用入口**：`TTFUrlUtils.openUrl(scheme:browser:)`（`TapTapSDK-Monorepo/iOS/TapTapSDK/TapTapRelation/Private/UI/Utils/TTFUrlUtils.swift:27`、`TapTapRelationLite/Private/Utils/TTFUrlUtils.swift:19`）

来源 URI（服务端 ClientSetting 下发）：
- `urls.relation_url.uri` / `urls.relation_add_friend_url.uri` / `urls.relation_notifications_url.uri`
- 自动追加 `sess_id` / `utm_sid` UUID（埋点 session）

**主站承接代码**：与 1.5 一致 — `AppDelegate.application(_:open:url:options:)` → `TapLaunchRouterManager.handleOpen(url:isPush:)` → `Router.push`

**MR 风险**：🔶 中 — 主站需保证 Router 能解析服务端返回的好友/通知页 URI；删除对应路由 → SDK 跳转 404

---

### 1.7 SDK 内嵌 WebView 跳第三方/客户端检测（TapTapMoment / TapTapLeaderboard）

**SDK 调用入口**：SDK 在 WebView 内 evaluateJavaScript 注入 `HAS_TAPTAP_CLIENT` 标志，让 H5 决定按钮是否展示客户端跳转：

```objc
// TapTapMoment/Private/View/TapMomentWebViewController.m:379
@"HAS_TAPTAP_CLIENT": @([[UIApplication sharedApplication] canOpenURL:[NSURL URLWithString:
  [TapMomentAPI shareInstance].isCN ? @"tapsdk://" : @"tapiosdk"]])
```

**主站承接代码**：仅依赖 `tapsdk://` Scheme 注册存在；具体跳转走 1.4 的统一 URL handler 链路。

**MR 风险**：✅ 低 — 只读 `canOpenURL` 结果；只要 Info.plist 中的 `tapsdk` Scheme 仍然注册，无需主站额外工作

---

### MR 速查：SDK 高风险文件

| 文件 | 所属能力 | 影响 |
|------|---------|------|
| `cn/TapTap/Info.plist` | 1.1 / 1.2 / 1.4 | ⚠️ `CFBundleURLSchemes` 中 `tapsdk` / `tapsdk2` / `taptap` / `taptaplane2/3/4` 不可删 |
| `cn/TapTap/TapTap.entitlements` | 1.3 | ⚠️ `applinks:` 五个域名 + App Group `group.taptap.share` 不可删 |
| `cn/TapTap/Login/viewModel/AuthManager.swift` | 1.2 | ⚠️ `shouldHandle(url:)` scheme/host 判定 + query 参数解析 key 名不可改 |
| `cn/TapTap/Login/VC/TapAuthViewController.swift` | 1.2 | ⚠️ `tapoauth://authorize` 回调拦截、`/authorize` Web URL 拼装契约不可改 |
| `cn/TapTap/Launch/Manager/TapLaunchRouterManager.swift` | 1.3 / 1.4 / 1.5 / 1.6 | ⚠️ `universalLinkHosts` 白名单、`convertToTapRoute` 的 `allowList`、`type=third_share` 识别、`uri` query 路由 — 任一变更 → SDK 唤端链路断 |
| `cn/TapTap/Launch/Manager/TapShareEventsFromGameManager.swift` | 1.3 | ⚠️ 剪贴板 read + NSKeyedUnarchiver 反序列化逻辑不可改，回写 result 字段名不可改 |
| `cn/TapTap/Base/Share/TapThirdEditorShareModel.swift` | 1.3 | ⚠️ 类名 `TapTap.TapThirdEditorShareModel` + Coding key 不可改 — SDK 已硬编码此类名 |
| `cn/TapTap/AppDelegate.swift`（`application(_:open:url:)` / `application(_:continue:)`） | 1.2/1.3/1.4 | 🔶 四个 handler 优先级顺序：`TapClientWebAuth → TapSocialPlatformManager → TapLaunchRouterManager → TapAliPaymentManager`，调换顺序可能拦截顺序错误 |
| `cn/TapTap/RouterRegister/TapRouterRegisterManager.swift` | 1.4/1.5/1.6 | 🔶 服务端下发的 URI 必须能被注册到的路由匹配；删除注册路由 → SDK 跳转 404 |

---

## 二、TapRouter 路由表契约

> 主站所有 SDK 跳转、Universal Link 落地、服务端 dispatch、桌面小组件唤起、App Extension 回主站、Push 通知打开、Shortcut 跳转 — 最终都汇聚到 `Router.push(uri, params:)`（TapRouter SPM 包）。**路由表是这些通道的公共契约文件，删除/重命名已注册 path 等价于 Android 删 `SchemePath.kt` 已上线路由。**

### 2.1 路由表定义文件

| 项目 | 说明 |
|------|------|
| 路由表 enum（端内） | `cn/TapTap/RouterRegister/TapRouterRegisterManager.swift` — `enum TapPageInsideIdentifier: String`（99 个 case） |
| 路由表 enum（端外/SDK 暴露） | 同文件 — `enum TapPageOutsideIndentifier: String`（67 个 case） |
| 路由注册调用 | 同文件 — `register(url:)` 调用 151 处 |
| 路由前缀解析 | `cn/TapTap/AppDelegate.swift:521` — `Router.registerURL(toKeyConvertor: "taptap://taptap.com/:module")` |
| dispatch URL 解析 | `cn/TapTap/AppDelegate.swift:530` — `https://d.taptap.com/tapiosnow/dispatch?uri=...` 拼成 `taptap://taptap.com{uri}` |
| 转换/白名单 | `cn/TapTap/Launch/Manager/TapLaunchRouterManager.swift:140-165` — `convertToTapRoute(url:).allowList = ["taptap","tapsdk","tapsdk2","taptaplane2/3/4"]` |
| Router 拦截器 | `cn/TapTap/RouterRegister/TapRouterRedirector.swift` |

### 2.2 SDK / Universal Link / Extension / Widget 已知硬依赖的关键 path

> 这些 path 一旦删除或重命名 rawValue，对应的外部唤端链路立即断 — **MR 评审时必须显式说明是否影响这些 path**。

| Path（rawValue） | enum case | 依赖来源 |
|------------------|-----------|----------|
| `app` | `tapGameDetailPage` / `appDetail` | TapTapShare fallback、TapTapAchievement、Widget（`taptap://app?game_id=...`）、Universal Link `m.taptap.cn/games/:id`、服务端 dispatch |
| `moment` | `tapMomentDetail` | TapTapShare 落地、Universal Link `m.taptap.cn/posts/:id`、动态分享回站 |
| `review` | `tapReviewDetailPage` | TapTapShare 评价分享、服务端 dispatch |
| `ranking` | （未声明 case，由 RouterRegister 动态注册） | `RankIntentIntent` Siri、`Router.push("taptap://ranking?opener=ios_spotlight")` |
| `user` | `tapUserProfilePage` | TapTapRelation 好友页 fallback、服务端 dispatch |
| `group-label` | `tapSubredditPage` | 论坛分享回站 |
| `notifications` | `tapMessagePage` | TapTapRelation `relation_notifications_url.uri`（服务端下发） |
| `add_friend` | `addContacts` | TapTapRelation `relation_add_friend_url.uri`（服务端下发） |
| `share-extension` | `shareExtension` | ShareExtension（图片分享）回主站 |
| `personalLetterShare` | `personalLetterShare` | PersonalLetter Extension 回主站 |
| `to` | `tapWebViewPage` | WebView JSBridge `openDeepLink` 唤起、SDK 内嵌 WebView 跳第三方页 |
| `wallet` | `walletPage` | 充值/钱包入口（服务端下发） |
| `home_tab_my` | `my` | Tab 切换 deeplink |
| `search` | `tapSearchPage` / `search`（外） | Shortcut `search` 跳转、Universal Link `m.taptap.cn/search` |
| `puzzle` | `puzzlePage` | 活动落地页（服务端下发） |
| `login-and-certify` | `userIdentifierVerify` | SDK 登录/实名认证回主站 |

> 完整清单：99 (TapPageInsideIdentifier) + 67 (TapPageOutsideIndentifier) = **166 个 case**，详见 `TapRouterRegisterManager.swift`。

### 2.3 路由前缀白名单（CFBundleURLSchemes 与 allowList 必须一致）

`TapLaunchRouterManager.convertToTapRoute.allowList`：
```
["taptap", "tapsdk", "tapsdk2", "taptaplane2", "taptaplane3", "taptaplane4"]
```

必须与 `cn/TapTap/Info.plist` 中的 `CFBundleURLSchemes` 保持一致 — 任何一侧增减都会导致：
- Info.plist 多于 allowList → 该 Scheme 进入主站后被 `convertToTapRoute` 强转为 `taptap://taptap.cn/...`，路径错乱
- allowList 多于 Info.plist → 该 Scheme 系统不会派发到 App，allowList 中的条目永远不触发

**MR 风险**：⚠️ 高
- `TapPageInsideIdentifier` / `TapPageOutsideIndentifier` 任一已上线 case 的 `rawValue` 不可改、不可删 — 等价 Android `SchemePath.kt` 已上线 path 锁定
- `register(url:)` 注册项不可删 — 即便 enum case 保留，未注册的 path 调用 `Router.push` 会失败
- `convertToTapRoute.allowList` 与 Info.plist `CFBundleURLSchemes` 必须双向同步
- `Router.registerURL(toKeyConvertor: "taptap://taptap.com/:module")` 模板不可改 — 是所有 `taptap://taptap.com/xxx` 形式路由的解析根
- `https://d.taptap.com/tapiosnow/dispatch?uri=...` dispatch 模板不可改 — 服务端短链/营销链都依赖

### 2.4 服务端驱动的 path（隐性依赖）

以下 path 由服务端 `ClientSettings.urls.*.uri` 字段下发给 SDK，**主站代码不直接引用，但删除对应 Router 注册会导致 SDK 跳转 404**：

| 服务端字段 | SDK 模块 | 主站需保证可路由的 path |
|-----------|---------|----------------------|
| `urls.achievement_my_list_url.uri` | TapTapAchievement | 成就页路由 |
| `urls.relation_url.uri` | TapTapRelation / RelationLite | 好友首页 |
| `urls.relation_add_friend_url.uri` | 同上 | 加好友页 |
| `urls.relation_notifications_url.uri` | 同上 | 好友通知页 |
| `urls.ios_rep_share_url.browser` | TapTapShare | 分享回站 Universal Link 落地路由 |

**MR 检查项**：删除任一路由前需在飞书项目 / 服务端 ClientSettings 配置库中反查是否被服务端引用，否则 SDK 端将静默断链。

---

## 三、端内容器 JS / Native API 契约（SCE / InstantGame / CloudGame）

> 主站托管运行第三方代码的三类容器：SCE（端内 SCE 游戏脚本）、InstantGame（H5 小游戏）、CloudGame（云游戏 H5 控制层）。容器 ↔ 容器内代码之间的 API 是稳定契约，**等价 Android 的「沙盒进程 AIDL（ISandboxCallTapService / ITapService）」**。这些 API 改动直接影响所有线上 SCE 游戏 / 小游戏 / 云游戏 H5。

### 3.1 SCE Bridge（主站 ↔ SCE 游戏脚本）

SCE 游戏脚本通过此 Objective-C bridge 调用主站能力（账号、广告、分享、成就、登录、充值、退出等）。

| 项目 | 说明 |
|------|------|
| 接口声明 | `cn/TapTap/Base/SCEModule/SCEBridge.h`（174 行，Objective-C protocol） |
| 实现 | `cn/TapTap/Base/SCEModule/SCEBridge.m`（231 行） |
| 容器入口 | `cn/TapTap/Base/SCEModule/SCEModule.swift` — `SCEModule.shared.startWithDidFinishLaunchingWithOptions` |
| 资源下载 | `cn/TapTap/Base/SCEModule/SCEDownload.swift` |
| 路由拦截 | `cn/TapTap/Base/SCEModule/SCERouteHooker.swift` |
| Urhox 适配 | `cn/TapTap/Base/SCEModule/SCEUrhoxAdapter.swift` |

主要接口分类（来自 SCEBridge.h）：
- 登录授权：`login:permissions:callback:` / `loginWithClientId:permissions:callback:` / `authorizeWithCompletion:`
- 引擎生命周期：`engineLaunched` / `engineReloadLaunched` / `engineDestroyed` / `engineLaunchFailed:`
- UI：`changeOrientation:` / `getNativeExitMenuRect` / `setShareboardHidden:`
- 分享：`showShareboardWithTemplateId:` / `fixedOnShareMessage:`
- 好友/成就：`openFriendList` / `setAchievementToastEnabled:` / `showAchievements` / `unlockAchievementWithId:`
- 广告：`SCEBridgAd`（loadWithCompletion / showWithCompletion / destroy）
- 风控：`isAdult`

**MR 风险**：⚠️ 高 — SCEBridge protocol 方法签名 / 回调参数结构 / 错误码契约任一变更 → 所有线上 SCE 游戏脚本立即断链（SCE 引擎独立打包发布，无法跟随主站强升）。**等价 Android `ISandboxCallTapService.aidl` 方法签名变更**。

### 3.2 InstantGame WXBridge（主站 ↔ 小游戏 H5）

H5 小游戏（兼容微信小游戏 API 子集）通过此 bridge 调用主站能力。

| 项目 | 说明 |
|------|------|
| 容器入口 | `package/InstantGame/Sources/InstantGame/` — `WebRuntimeContainer` / `GameWebViewController` |
| Bridge 模块（78 个 .swift 文件） | `package/InstantGame/Sources/InstantGameBuildinModules/WXBridge/` |
| Bridge 分类目录 | `AD/`、`Basics/`、`DataAnalysis/`、`DebugFeedback/`、`Device/`、`FileSystem/`、`OpenInterface/`（含 `Achievement/`）、`Performance/`、`Review/`、`Share/`、`UserInterface/` |
| 跨 WebView 动态注册 | `package/InstantGame/Sources/InstantGameBuildinModules/WXBridge/UserInterface/TapLeaderboard.swift:558` — `TapWebViewJSBridgeManager.shared.registerHandler(identifier:)` 将排行榜 JSBridge 动态注入主站 WebView |
| Console 日志桥 | `package/InstantGame/Sources/InstantGame/Runtime/WebContainer/WebRuntimeContainer+Console.swift` — `messageHandlers.registerLogStorageURL` / `messageHandlers.console` |
| 主站接入点 | `cn/TapTap/AppDelegate.swift:136` — `TapMinigameManager.shared.setup()` + `ADModule.setExternalProvider(InstantGameADProviderImpl(...))` |
| IAP 适配 | `cn/TapTap/Base/Minigame/TapMinigameIAPAdapter.swift`（`InstantGameIAPProvider` 协议实现） |
| 留存适配 | `cn/TapTap/Base/Minigame/TapMinigameRetentionProvider.swift`（`InstantGameRetentionProvider` 协议实现） |

**MR 风险**：⚠️ 高 — WXBridge API 名称、参数 schema、回调 schema 是小游戏开发者的公开契约（兼容微信小游戏子集）；主站侧 `InstantGameADProvider` / `InstantGameIAPProvider` / `InstantGameRetentionProvider` 协议方法签名变更 → InstantGame SPM 包内调用断 → 所有上线小游戏受影响

### 3.3 CloudGame H5 接口（主站 ↔ 云玩 H5）

| 项目 | 说明 |
|------|------|
| 入口适配 | `cn/TapTap/PlayGame/CloudGame/InGame/Adapters/CloudGameHMAdapter+OAuthLogin.swift` |
| 容器目录 | `cn/TapTap/PlayGame/CloudGame/` |
| WebView JSBridge action | 主站 WebView JSBridge 的 `CloudGameMessageHandler`（参考 Android 文档 2.1） |

**MR 风险**：🔶 中 — 云玩游戏供应商对接接口，改动需协调外部厂商

### 3.4 容器契约速查

| 文件 | 影响 |
|------|------|
| `cn/TapTap/Base/SCEModule/SCEBridge.h` | ⚠️ 方法签名 / 回调 schema 不可改 — 影响所有线上 SCE 游戏 |
| `cn/TapTap/Base/SCEModule/SCEModule.swift` | ⚠️ 容器生命周期入口，变更影响 SCE 启停 |
| `package/InstantGame/Sources/InstantGameBuildinModules/WXBridge/**` | ⚠️ 78 个 bridge 文件，API 名称 / 参数 schema 是小游戏公开契约 |
| `cn/TapTap/Base/Minigame/TapMinigameIAPAdapter.swift` | ⚠️ `InstantGameIAPProvider` 协议实现，方法签名变更影响所有小游戏 IAP |
| `cn/TapTap/Base/Minigame/TapMinigameRetentionProvider.swift` | 🔶 `InstantGameRetentionProvider` 留存能力，影响所有小游戏退出挽留 |
| `package/InstantGame/Sources/InstantGameBuildinModules/WXBridge/UserInterface/TapLeaderboard.swift` | 🔶 通过 `TapWebViewJSBridgeManager.shared.registerHandler` 注入排行榜 JSBridge，与主站 WebView JSBridge 协议绑定 |
| `cn/TapTap/PlayGame/CloudGame/` | 🔶 云玩适配层 |

---

## 四、社交平台登录回调（QQ / 微信 / Apple）

> 主站作为登录方调用三方 SDK 后，三方应用回调时需要承接。这是「调用方→TapTap」反向链路，但与 SDK 调用同样基于 `application(_:open:url:)` / `application(_:continue:)`。

| 平台 | URL Scheme（callback） | Universal Link | 注册方式 | 代码路径 |
|------|-----------------------|----------------|---------|----------|
| QQ | `tencent101528186` | `applinks:www.taptap.com`（共用） | `TencentOAuth.init(appId:andUniversalLink:andDelegate:)` | `cn/TapTap/Login/Social/TapSocialPlatformQQ.swift`（25-90） |
| 微信 | `wx69c85f43cdf28209` | 同上 | `WXApi.registerApp(appKey, universalLink:)` | `cn/TapTap/Login/Social/TapSocialPlatformWechat.swift`（26-95） |
| Apple | 无 Scheme（系统 ASAuthorization） | — | `com.apple.developer.applesignin = Default`（entitlements） | `cn/TapTap/Login/Social/TapSocialPlatformApple.swift` |
| 支付宝 | 无主动注册（仅作 `LSApplicationQueriesSchemes` 探测：`alipays`/`alipayconnect`） | 内部 `safepay`/`safepay_global` 走 `dispatch.taptap.cn/tapiosnow/` | `AlipaySDK.defaultService().payOrder(...)` | `cn/TapTap/Base/Payment/TapPaymentManager.swift`（373-435） |

`AppDelegate` 分发：`TapSocialPlatformManager.shared.handleOpen(url:option:)` 遍历已注册平台依次 `handleOpen` / `handleOpenUniversalLink`。

**MR 风险**：⚠️ 高 — `tencent101528186` / `wx69c85f43cdf28209` Scheme 与三方 App 后台注册绑定，不可改；改动 → 第三方 SDK 回调失效

---

## 五、WebView JSBridge（WKWebView）

### 5.1 主站 WebView JSBridge（TapTapAPI）

`window.TapTapAPI(action, params)` 统一入口，**白名单校验**：仅 `dataSource.webViewTrustedDomainsDomains()` 中的 host 可调用。

| 项目 | 说明 |
|------|------|
| 注册方式 | `userController.add(WeakScriptMessageDelegate(delegate: self), name: "TapTapAPI")` |
| 消息接收 | `TapWebViewController.userContentController(_:didReceive:)` |
| 多 Bridge 分发 | `TapWebViewJSBridgeManager.shared.handleJSBridgeCall(action:params:webViewController:)`（动态注册 Handler 模式） |
| 默认实现位置 | `package/TapWebViewController/Sources/TapWebViewController/TapWebViewController+Script.swift`（819 行） |
| 主站业务实现 | `cn/TapTap/WebView/TapWebViewDelegate.swift`（1466 行） |

支持的 message action：

| 类别 | action |
|------|--------|
| 分享 | `openShareWindow` / `openImgShareWindow` / `toggleShareBtn` |
| 登录 | `login` / `getLoginCertificate` / `openClientSwitchAccount` |
| 浏览器/外链 | `openBrowser` / `openDeepLink` / `openFullscreenImg` |
| WebView 控制 | `closeWebView` / `setWebViewDisplay` / `toggleNavbar` / `toggleAutoLockScreen` / `toggleWebContentAutoMoveUp` / `setDeviceOrientation` |
| 系统能力 | `showToast` / `tapLog` / `copyToPasteboard` / `executeJsOnTargetWeb` / `closeTargetWeb` |
| 主站业务（cn/TapTap/WebView/TapWebViewDelegate.swift:296） | `openCustomerService` / `openAppStore` / `saveImage` / `postGameRecordEvent` / `bindThirdGameRecord` / `clientGoToMomentPublishPage` / `topicComplaintSuccessEvent` / `directDelivery` / `sendGameInviteFriendMessage` / `buyTapGame` / `getCookie` / `setCookie` / `listenMediaVolumeChange` / `momentActivityEnrolledEvent` |

回调通道（H5 接收）：`window.webviewEmit(funcName, jsonStr)`（如 `onDeepLinkOpen` / `onVolumeChange` / `shareSuccess` / `onDeviceOrientationChange`）

**MR 风险**：🔶 中 — `TapTapAPI` 这个 messageHandler name 一旦改动需同步全部 H5 端；action 名称变更需同步 H5 协议；白名单 `webViewTrustedDomainsDomains()` 受 `Configs` 服务端下发管控

---

### 5.2 SDK 登录授权 WebView（独立 JSBridge）

`TapAuthViewController` 自己注册 `TapTapAPI` 同名 messageHandler，但 action 集合不同（专用于授权场景）。

| 项目 | 说明 |
|------|------|
| 注册方式 | `userController.add(WeakScriptMessageDelegate(delegate: self), name: "TapTapAPI")` |
| 代码路径 | `cn/TapTap/Login/VC/TapAuthViewController.swift`（120 / 522-560） |
| 支持 action | `getLoginCertificate` / `closeWebView` / `openClientSwitchAccount` / `clientSendTrack` |

**MR 风险**：🔶 中 — action 协议与 `accounts.taptap.cn/authorize` H5 协议绑定，需同步变更

---

### 5.3 三方应用绑定 WebView（TapThirdBindWebView - JS 注入到三方域）

> 等价 Android 2.3 `InjectJsWebView` — 主站打开三方游戏官网/账号绑定页时，向三方域 WebView 注入自定义 JS，桥接 cookie 读写、JS 执行、关闭通知。这是合作伙伴对接的契约面。

| 项目 | 说明 |
|------|------|
| 代码路径 | `cn/TapTap/WebView/TapThirdBindWebViewController.swift`（388 行） / `cn/TapTap/WebView/TapGameBindWebView.swift`（768 行） |
| 用途 | 主站打开三方游戏官网/账号绑定页，桥接 cookie 读写、JS 注入、关闭通知 |
| 关联 JSBridge action | `executeJsOnTargetWeb` / `closeTargetWeb` / `getCookie` / `setCookie` / `openTargetWebWithJS` |
| 注入配置 | `jsbObjName` / `callbackMethodName` / `userAgent` / `js` |

**MR 风险**：⚠️ 高 — `executeJsOnTargetWeb` / `closeTargetWeb` 等 action 名 + 入参 schema 是合作伙伴接入契约；`getCookie` / `setCookie` 行为变更可能影响合作方账号互通

---

## 六、App Extensions

### 6.1 ShareExtension（系统分享 - 图片）

| 项目 | 说明 |
|------|------|
| Extension 类型 | Share Extension（`com.apple.share-services`） |
| 入口类 | `cn/ShareExtension/ShareViewController.swift`（SLComposeServiceViewController） |
| 激活规则 | `NSExtensionActivationSupportsImageWithMaxCount = 9`（最多 9 张图片） |
| App Group | `group.taptap.share`（`cn/ShareExtension/ShareExtension.entitlements`） |
| 数据存储 | `group.taptap.share` 容器目录 / `taptap.share.images` key 下的归档图片数据 |
| 回主站跳转 | `taptap://share-extension?opener=photo_sdk` |
| Info.plist | `cn/ShareExtension/Info.plist`（1-21） |

流程：系统分享面板选 TapTap → ShareExtension 接收图片 → 序列化到 App Group 共享目录 → `extensionContext.open(URL("taptap://share-extension?opener=photo_sdk"))` 唤起主站 → 主站路由 `share-extension` 读取共享目录内图片 → 弹发布器

**MR 风险**：⚠️ 高
- App Group `group.taptap.share` 不可改 — 牵连 ShareExtension/Widget/NotificationService/PersonalLetter
- `taptap://share-extension` Scheme path 不可改 — 主站路由需保持
- `taptap.share.images` 与 `imagesKey` 常量需主站/Extension 双端同步
- `NSExtensionActivationSupportsImageWithMaxCount` 变更影响系统分享面板可见性

---

### 6.2 PersonalLetter Extension（系统分享 - 文本/链接 / Siri Intent）

| 项目 | 说明 |
|------|------|
| Extension 类型 | Share Extension（`com.apple.share-services`）+ `IntentsSupported: INSendMessageIntent` |
| 入口类 | `cn/PersonalLetter/ShareViewController.swift` |
| 激活规则 | `NSExtensionActivationSupportsText = true` + `NSExtensionActivationSupportsWebURLWithMaxCount = 1` |
| App Group | `group.taptap.share` |
| 数据存储 key | `com.share.personalLetter.content` |
| 回主站跳转 | `taptap://personalLetterShare` |
| Info.plist | `cn/PersonalLetter/Info.plist` |

**MR 风险**：⚠️ 高 — App Group + Scheme path + Key 名同上规则

---

### 6.3 NotificationService Extension（富推送）

| 项目 | 说明 |
|------|------|
| Extension 类型 | UNNotificationServiceExtension |
| 入口类 | `cn/NotificationService/NotificationService.swift` |
| App Group | `group.taptap.share`（读取 `com.taptap.xua` key 用于鉴权回执） |
| 推送回执接口 | `https://api.taptapdada.com/push-receipt/v1/ios` |
| 功能 | 下载 `userInfo["image_url"]` 图片附件 + 上报 arrival 回执 |
| Info.plist | `cn/NotificationService/Info.plist` |

**MR 风险**：🔶 中 — App Group / 共享 key `com.taptap.xua` 协议与主站 `AppDelegate.setupWidget` 写入逻辑绑定（同步在 1.3 同款 App Group）

---

### 6.4 TapTapWidget（桌面小组件）

| Widget Kind | 实现类 | 入参/跳转 Scheme |
|------------|--------|-----------------|
| `TapTapWidget` | 日历组件（`cn/TapTapWidget/TapTapWidget.swift`） | `taptap://app?game_id={id}&opener=widget_appcalendar` |
| `TapTapRecentGamesWidget` | 最近玩过 - 小/中尺寸（`cn/TapTapWidget/TapTapRecentGamesWidget.swift`） | 通过 App Group `group.taptap.share` 读取主站写入的最近游戏列表 |
| `TapTapRankWidget` | 排行榜组件（`cn/TapTapWidget/TapTapRankWidget.swift`） | `taptap://app?game_id={id}&opener=widget_rank` / `taptap://craft/detail?game_id={id}&opener=widget_rank` |
| `TapTapTownWidget` | TapTap 小镇组件（`cn/TapTapWidget/TapTapTownWidget.swift`） | — |

| 项目 | 说明 |
|------|------|
| Bundle 入口 | `cn/TapTapWidget/TapTapWidgetBundle.swift`（@main） |
| Entitlements | `cn/TapTapWidgetExtension.entitlements` — `application-groups: group.taptap.share` |
| 主站数据同步 | `AppDelegate.setupWidget()` 写入 `com.taptap.xua` / `accessToken`；`RecentGamesDataSync.shared.startMonitoring()` 同步最近游戏 |

**MR 风险**：⚠️ 高
- Widget Kind 名（`TapTapWidget` / `TapTapRecentGamesWidget` / `TapTapRankWidget` / `TapTapTownWidget`）一旦变更 → 已添加到桌面的小组件失效（需用户重新添加）
- App Group key 名 `com.taptap.xua` 不可改 — 双端读写依赖
- `taptap://app?game_id=...&opener=widget_*` 路由不可删

---

### 6.5 NSUserActivity / App Intents（iOS 17+）

| 类型 | activityType / IntentName | 处理代码 |
|------|--------------------------|---------|
| Rank Intent（Siri） | `RankIntentIntent`（`AppDelegate.swift:24`） | `AppDelegate.application(_:continue:)` → `Router.push("taptap://ranking?opener=ios_spotlight")` |
| INSendMessageIntent | 系统建议 | PersonalLetter Extension（4.2） |
| Spotlight 搜索 | `TapSystemSearchTool.systemQueryActivityType` | `TapSystemSearchTool.generateUri/generateUrl` |
| TapSearchIntent | App Intents | `cn/TapTap/AppIntents/TapAppIntentsManager.swift:18` |
| TapPublishIntent | App Intents | `cn/TapTap/AppIntents/TapAppIntentsManager.swift:43` |
| TapScanCodeIntent | App Intents | `cn/TapTap/AppIntents/TapAppIntentsManager.swift:68` |
| TapForumIntent | App Intents | `cn/TapTap/AppIntents/TapAppIntentsManager.swift:93` |

**MR 风险**：🔶 中 — `RankIntentIntent` activityType 与系统/Siri 已暴露的 NSUserActivity 注册绑定；NSUserActivityTypes 在 Info.plist 中声明（`INSendMessageIntent` / `RankIntentIntent`），删除会影响 Siri Shortcut

---

## 七、UIApplicationShortcutItems（3D Touch / 长按图标）

| Type | Title | 处理代码 |
|------|-------|--------|
| `search` | 搜索 | `AppDelegate.application(_:performActionFor:completionHandler:)` → `Router.push(TapShortcutItemType.search.uri)` |
| `taptapai` | TapTap AI | 同上 |
| `scan` | 扫码 | 同上 |
| `post` | 发布 | 同上 |

代码路径：`cn/TapTap/AppDelegate.swift`（374-388） / `cn/TapTap/Info.plist`（147-181）

**MR 风险**：🔶 中 — Type 字符串变更不影响外部 SDK，但变更后用户首次升级会丢失自定义 Shortcut；图标名（`shortcut_ai` / `shortcut_scan`）需保留对应资源

---

## 八、推送唤起

| 通道 | 说明 | 代码路径 |
|------|------|---------|
| APNs Token 注册 | `AppDelegate.didRegisterForRemoteNotificationsWithDeviceToken` → `TapNotificationManager.didRegisterForRemoteNotifications` | `cn/TapTap/NotificationManager/TapNotificationManager.swift` |
| 在线点击处理 | `userNotificationCenter(_:didReceive:withCompletionHandler:)` → `didReceiveRemoteNotification(userInfo:)` → `TapLaunchRouterManager.handleOpen(url:isPush:true)` | 同上 |
| 静默推送 | `AppDelegate.application(_:didReceiveRemoteNotification:fetchCompletionHandler:)` → 红点刷新等 | `cn/TapTap/AppDelegate.swift`（617-637） |
| 富文本扩展 | `cn/NotificationService/NotificationService.swift`（见 6.3） | — |
| 离线推送通道 | 仅依赖 APNs（iOS 不需要厂商通道） | — |

**Entitlements**：`aps-environment = development / production` / `com.apple.developer.usernotifications.communication`

**MR 风险**：🔶 中 — `userInfo` 中的 `red_point_reminder` action 字段、`image_url` 字段是服务端推送 payload 契约，变更需服务端同步

---

## 九、Universal Link 整体白名单（Associated Domains）

> 已在 1.3 / 1.4 引用，此处汇总用于排查 entitlements / apple-app-site-association 配置一致性。

| 域名 | 用途 |
|------|------|
| `www.taptap.com` / `www.taptap.cn` | 主站官网 → app 跳转 |
| `d.taptap.com` / `d.taptap.cn` | 短链/dispatch 跳转 |
| `dispatch.taptap.com` / `dispatch.taptap.cn` | 第三方分享/支付回跳 dispatch |

DEBUG 额外支持：`dispatch-beta.xdrnd.cn`（仅 `TapLaunchRouterManager.universalLinkHosts`）

**MR 风险**：⚠️ 高 — `applinks:` 域名列表与 `TapLaunchRouterManager.universalLinkHosts` 必须保持一致；任意一侧更新需双向同步；删除任一域名 → 该域名 Universal Link 落地直接跳浏览器

---

## 十、剪贴板能力（Pasteboard）

| 场景 | 主站行为 | 关联 SDK |
|------|---------|---------|
| 三方分享数据交换 | 读 `pasteboard.items.first["data"]`（NSKeyedArchiver TapThirdEditorShareModel）+ 写回 result | TapTapShare（见 1.3） |
| 口令分享监听 | `TapShareTokenListener.setup()`（启动后启用） | 主站内部能力 |

代码路径：`cn/TapTap/Launch/Manager/TapShareEventsFromGameManager.swift`（66-138） / `cn/TapTap/Launch/Manager/TapShareTokenListener.swift`

**MR 风险**：⚠️ 高 — 剪贴板数据交换 schema（key "data"、value Data 类型、NSKeyedArchiver 类名 `TapTap.TapThirdEditorShareModel`）与 SDK 端硬编码一致，不可改

---

## 十一、外部应用查询（LSApplicationQueriesSchemes）

> 50 条上限，用于 `canOpenURL` 探测外部应用是否安装（影响游戏列表/分享/正版校验等场景）。

| 类别 | 包含 schemes |
|------|------------|
| 登录回调辅助 | `mqq*` / `tencentapi.qq.reqContent:` / `mqqOpensdkSSoLogin` / `mqqconnect` / `mqqopensdk*` |
| 微信 | `weixin` / `weixinULAPI` |
| 支付 | `alipays` / `alipayconnect` |
| 游戏厂商 / 内容平台（用于上报已安装游戏） | `bilibili` / `kwai` / `pinduoduo` / `taobao` / `xhsdiscover` / `dewuapp` / `sinaweibo` / `homework` / `steammobile` / `heybox` / `yuanshen` / `huputiyu` / `bilibili` / `instagram` / `youtube` / `twitter` / `quark` / `ucbrowser` 等 |

启动后通过 `SchemeTool.uploadIfNeed()`（`cn/TapTap/Tools/SchemeTool.swift`）每 24h 上报已安装游戏 scheme 列表，作为推荐系统输入。

**MR 风险**：🔶 中
- `loginSchemePrifixs = ["mqq", "weixin", "tencentapi"]` 不可改，否则会把登录 scheme 当游戏 scheme 上报
- 新增 scheme 时注意上限 50 条，超过会被系统截断
- 上报接口 `reportApkList` 协议变更需服务端同步

---

### MR 速查：高风险文件总表

| 文件 | 影响 |
|------|------|
| `cn/TapTap/Info.plist` | ⚠️ `CFBundleURLSchemes` / `LSApplicationQueriesSchemes` / `UIApplicationShortcutItems` / `NSUserActivityTypes` 任一变更影响外部唤起 |
| `cn/TapTap/TapTap.entitlements` | ⚠️ `applinks:` 五个域名、`com.apple.developer.applesignin`、App Group `group.taptap.share` 不可删 |
| `cn/TapTap/AppDelegate.swift`（`application(_:open:url:)` / `application(_:continue:userActivity:)`） | ⚠️ 四个 handler 优先级顺序变更可能导致 Scheme 被错误 handler 拦截 |
| `cn/TapTap/Login/viewModel/AuthManager.swift` | ⚠️ SDK OAuth 登录参数协议 |
| `cn/TapTap/Login/VC/TapAuthViewController.swift` | ⚠️ `tapoauth://authorize` 回调拦截 + WebView JSBridge action 集合 |
| `cn/TapTap/Login/Social/TapSocialPlatformQQ.swift` / `TapSocialPlatformWechat.swift` | ⚠️ AppID / UniversalLink 与三方平台后台绑定，不可改 |
| `cn/TapTap/Launch/Manager/TapLaunchRouterManager.swift` | ⚠️ `universalLinkHosts` / `convertToTapRoute.allowList` / `type=third_share` 识别 / `uri` query 路由 |
| `cn/TapTap/Launch/Manager/TapShareEventsFromGameManager.swift` | ⚠️ 剪贴板 read + NSKeyedUnarchiver 反序列化 |
| `cn/TapTap/Base/Share/TapThirdEditorShareModel.swift` | ⚠️ NSKeyedArchiver 类名 `TapTap.TapThirdEditorShareModel` + Coding key |
| `cn/TapTap/Base/Payment/TapPaymentManager.swift`（`TapAliPaymentManager`） | ⚠️ Alipay `fromScheme: "taptap"` / `fromUniversalLink: "https://dispatch.taptap.cn/tapiosnow/"` 必须与支付宝后台配置一致 |
| `cn/ShareExtension/ShareViewController.swift` + `Info.plist` + `entitlements` | ⚠️ App Group + 图片归档 key + `taptap://share-extension` 路由 |
| `cn/PersonalLetter/ShareViewController.swift` + `Info.plist` + `entitlements` | ⚠️ App Group + 文本 key + `taptap://personalLetterShare` 路由 |
| `cn/NotificationService/NotificationService.swift` + `entitlements` | 🔶 App Group + `com.taptap.xua` key + 推送回执 API |
| `cn/TapTapWidget/*` + `cn/TapTapWidgetExtension.entitlements` | ⚠️ Widget Kind 名 + App Group + `taptap://app?game_id=...&opener=widget_*` 路由 |
| `cn/TapTap/AppIntents/TapAppIntentsManager.swift` | 🔶 App Intents（`TapSearchIntent` / `TapPublishIntent` / `TapScanCodeIntent` / `TapForumIntent`）类名是系统层契约，变更后已绑定的 Siri Shortcut 失效 |
| `cn/TapTap/Tools/SchemeTool.swift` | 🔶 `loginSchemePrifixs` 白名单不可改；游戏 schemes 上报接口字段不可改 |
| `package/TapWebViewController/Sources/TapWebViewController/TapWebViewController+Script.swift` | 🔶 `TapTapAPI` messageHandler name + action 集合 — 协议层变更需同步 H5 端 |
| `cn/TapTap/WebView/TapWebViewDelegate.swift` | 🔶 主站业务 JSBridge action 实现层 |
| `cn/TapTap/RouterRegister/TapRouterRegisterManager.swift` | ⚠️ **路由表契约文件**：`TapPageInsideIdentifier`（99 case）+ `TapPageOutsideIndentifier`（67 case）+ 151 处 `register(url:)` — 任一已上线 `rawValue` 不可改、不可删，等价 Android `SchemePath.kt`。完整说明见第二章 |
| `cn/TapTap/RouterRegister/TapRouterRedirector.swift` | 🔶 Router 拦截重定向逻辑，变更影响全站路由分发 |
| `cn/TapTap/Base/SCEModule/SCEBridge.h` / `SCEBridge.m` | ⚠️ **SCE 容器契约**：方法签名/回调 schema 不可改，影响所有线上 SCE 游戏（等价 Android `ISandboxCallTapService.aidl`） |
| `cn/TapTap/Base/SCEModule/SCEModule.swift` | ⚠️ SCE 容器生命周期入口 |
| `package/InstantGame/Sources/InstantGameBuildinModules/WXBridge/**`（78 文件） | ⚠️ **小游戏容器契约**：API 名称/参数/回调 schema 是小游戏开发者公开契约，兼容微信小游戏子集 |
| `cn/TapTap/Base/Minigame/TapMinigameIAPAdapter.swift` | ⚠️ `InstantGameIAPProvider` 协议实现，签名变更影响所有小游戏 IAP |
| `cn/TapTap/Base/Minigame/TapMinigameRetentionProvider.swift` | 🔶 `InstantGameRetentionProvider` 协议实现 |
| `cn/TapTap/PlayGame/CloudGame/` | 🔶 云玩 H5 适配层，改动需协调外部厂商 |

---

*以上为当前代码全量梳理（主目录：`tap-main/ios/cn`，对照 SDK：`TapSDK-Monorepo/iOS/TapTapSDK`），后续如有新增交互点请同步更新本文档。*
