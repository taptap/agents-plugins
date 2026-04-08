# TapTap SDK Android 三方 - 调用 TapTap 主站交互能力梳理

梳理范围：Android TapSDK 各模块（tap-license、tap-share、tap-achievement、tap-review、tap-rep、tap-relation、tap-relation-lite）中所有向 TapTap 主站客户端或主站 H5 页面发起调用的代码路径。

更新时间：2026-03-31

---

## 1. 正版验证（License）：Scheme 拉起 TapTap 客户端

SDK 在进行正版验证时，优先通过自定义 Scheme 直接拉起 TapTap App，跳转到指定游戏的购买/验证页面。

### 国区实现（CNIabService）

| 项目 | 说明 |
| --- | --- |
| 文件路径 | sdk/tap-license/.../billingservice/CNIabService.kt |
| 方法 | openTapTap() |
| 目标包名 | 优先 com.taptap.pad，回退 com.taptap |
| Scheme | taptap://taptap.com/app?identifier={gamePackageName}&license=yes |
| Intent 构造 | setData(Uri.parse(uri)) + setPackage(getPackageName()) + FLAG_ACTIVITY_NEW_TASK |
| 失败回退 | ACTION_VIEW → https://www.taptap.com/mobile |

**调用流程：**
1. 检查是否安装 TapTap CN（getPackageName() 检测 com.taptap.pad / com.taptap）
2. 构造 `taptap://taptap.com/app?identifier=...&license=yes` 并 startActivity
3. 若 startActivity 抛出异常，回退打开 https://www.taptap.com/mobile

### 国际区实现（GlobalIabService）

| 项目 | 说明 |
| --- | --- |
| 文件路径 | sdk/tap-license/.../billingservice/GlobalIabService.kt |
| 方法 | openTapTap() |
| 目标包名 | com.taptap.global |
| Scheme | tapglobal://taptap.tw/app?identifier={gamePackageName}&license=yes |
| Intent 构造 | setData(Uri.parse(uri)) + setPackage("com.taptap.global") + FLAG_ACTIVITY_NEW_TASK |
| 失败回退 | ACTION_VIEW → https://www.taptap.com/mobile |

**特殊场景：**
若设备同时安装国区和国际区 TapTap，TapLicenseFragment.checkLicenseBothRegion() 先验 CN 再验 Global，均未购买时弹出选择弹窗（showLicenseChooserDialog()）。正版验证结果通过广播（ACTION_PAY_CHANGED）和 Activity 生命周期双通道回收，onActivityResult 中处理 com.play.taptap.billing.CheckLicenseAct 返回结果。

---

## 2. 正版验证（License）：引导下载 TapTap H5 页

当设备未安装任何版本 TapTap 客户端时，弹出「下载 TapTap」弹窗，用户点击后跳转主站 H5 下载页。

| 项目 | 说明 |
| --- | --- |
| 文件路径 | sdk/tap-license/.../internal/TapLicenseFragment.kt 第 85–93 行 |
| 触发位置 | dialogClickListener.onDownloadTapTap() 回调 |
| 目标 URL | https://www.taptap.com/mobile |
| Intent 类型 | ACTION_VIEW + FLAG_ACTIVITY_NEW_TASK |

**调用流程：**
1. checkLicense() 检测 cnIabService.hasInstalled == false && globalIabService.hasInstalled == false
2. UIUtil.showNotInstalledDialog() 弹出未安装提示
3. 用户点击「下载 TapTap」→ onDownloadTapTap() → startActivity(ACTION_VIEW, "https://www.taptap.com/mobile")

---

## 3. DLC 购买 / 查询：拉起 TapTap 内购页

DLC 购买和查询通过 com.play.taptap.billing.InAppBillingAct Action 跳转至 TapTap 客户端内的内购页面。

| 项目 | 说明 |
| --- | --- |
| 文件路径 | sdk/tap-license/.../internal/TapLicenseFragment.kt |
| 方法 | queryDLC(skuList) / purchaseDLC(skuId) |
| Action | com.play.taptap.billing.InAppBillingAct |
| 参数 | cmd=query/order、pkg={gamePackageName}、sku/price/title/description（购买时） |
| 通信方式 | startActivityForResult，结果通过 onActivityResult 回调 |
| 未安装处理 | UIUtil.showNotInstalledDialog() 弹出引导弹窗 |

**调用流程：**
1. 构造 Intent（Action = com.play.taptap.billing.InAppBillingAct，附带游戏包名和 SKU 信息）
2. packageManager.queryIntentActivities() 检测是否可响应
3. 已安装：startActivityForResult 拉起 TapTap 内购页
4. onActivityResult 解析 ACTIVITY_RESPONSE_CODE 获得购买结果

---

## 4. 图片分享至 TapTap（tap-share 模块）

SDK 提供将游戏截图等图片直接分享到 TapTap 客户端（国服）的能力。

| 项目 | 说明 |
| --- | --- |
| 文件路径（主逻辑） | sdk/tap-share/.../TapTapShare.kt |
| 文件路径（工具类） | sdk/tap-share/.../utils/TapTapShareUtil.java |
| 方法 | TapTapShare.share(activity) |
| 目标包名 | 硬编码 com.taptap（仅支持国服） |
| Intent Action | ACTION_SEND_MULTIPLE，MIME type image/* |
| URI 权限 | grantUriPermission("com.taptap", uri, FLAG_GRANT_READ_URI_PERMISSION) |
| Manifest 声明 | `<package android:name="com.taptap" />`（Android 11+ 可见性） |

**调用流程：**
1. TapTapShareUtil.checkTapTapInstall(activity)：检测 com.taptap 是否已安装
2. TapTapShareUtil.checkTapTapSupportShare(activity)：检测是否能响应 ACTION_SEND_MULTIPLE
3. 校验通过：shareIntent.setPackage("com.taptap") + startActivity(shareIntent)
4. 校验失败：ACTION_VIEW 打开 failUrl（开发者传入）或服务端下发的回退 URL

**特殊场景：**
- 仅支持国服客户端（com.taptap），不支持国际版（com.taptap.global）
- 图片使用 FileProvider URI，需提前授权读权限

---

## 5. 成就页：Deeplink 跳转 TapTap 客户端（tap-achievement 模块）

展示成就列表时优先通过 Deeplink 打开 TapTap 客户端内的成就页，未安装时降级为 WebView 内嵌页。

| 项目 | 说明 |
| --- | --- |
| 文件路径 | sdk/tap-achievement/.../internal/TapAchievementInternal.kt |
| 方法 | showAchievements() |
| 目标包名 | getTapPkgName()（CN→com.taptap，Global→com.taptap.global） |
| URI 来源 | initializerService.getAchievementUrl(type = "uri")（服务端初始化时下发） |
| Intent 构造 | setData(Uri.parse(url)) + setPackage(getTapPkgName()) + FLAG_ACTIVITY_NEW_TASK |
| 降级方案 | 未安装时弹出 AchievementWebFragment（WebView 内嵌） |

**调用流程：**
1. isTapInstalled() 检测当前区域对应 TapTap 包是否安装
2. 已安装：请求成就 URI → startActivity 跳转客户端
3. 未安装：AchievementWebFragment.show() 展示内嵌 WebView

---

## 6. 评价页：Deeplink 跳转 TapTap 客户端（tap-review 模块）

SDK 引导用户在 TapTap 客户端内发布游戏评价，需先获取 cross-app-code 做跨应用身份认证。

| 项目 | 说明 |
| --- | --- |
| 文件路径 | sdk/tap-review/.../internal/TapReviewInternal.kt |
| 方法 | openReview() |
| URI 来源 | initializerService.getReviewUrl("uri")（服务端下发） |
| 跨应用认证 | 追加 tapsdk_cross_app_code 参数（服务端 API 获取） |
| 游戏标识 | 追加 sdk_identifier={gamePackageName} |
| Intent 构造 | setData(finalUri) + FLAG_ACTIVITY_NEW_TASK（不指定包名，由系统路由） |
| 未安装处理 | goTapDownloadPage()：ACTION_VIEW 打开 initializerService.getReviewUrl("browser") |

**调用流程：**
1. isTapInstalled() 检测
2. 未安装 → 弹 Toast + ACTION_VIEW 打开服务端下发的 browser URL
3. 已安装 → 请求 cross_app_code → 构造最终 URI（附加 tapsdk_cross_app_code + sdk_identifier）→ startActivity

---

## 7. REP 推荐位：跳转 TapTap 客户端或 H5（tap-rep 模块）

REP（推荐位）模块根据服务端返回的 uri（客户端 Deeplink）或 url（H5）决定跳转目标，优先拉起客户端。

| 项目 | 说明 |
| --- | --- |
| 文件路径 | sdk/tap-rep/.../internal/TapRepInternal.kt |
| 方法 | open(openUrl, callback) |
| URI 来源 | 服务端接口 RepRepository.getRepLink(openUrl) 返回 RepResponse.uri / RepResponse.url |
| 跳转逻辑 | 已安装 TapTap 且 uri 非空 → 用 uri（附加 ch_src 归因参数）；否则用 url |
| Intent 构造 | ACTION_VIEW + setData(clientUri) + FLAG_ACTIVITY_NEW_TASK |

**调用流程：**
1. 请求服务端 REP 链接接口，获取 uri（Deeplink）和 url（H5 回退）
2. isTapInstalled() && uri.isNotEmpty() → 使用客户端 Deeplink，追加 ch_src 归因参数
3. 否则 → 使用 H5 url
4. 统一 ACTION_VIEW 跳转，由系统或浏览器路由

---

## 8. 关系链：跳转 TapTap 用户/游戏页（tap-relation / tap-relation-lite 模块）

关系链模块提供 goTapTap() 和 goGame() 两个跳转函数，分别跳转 TapTap 用户主页/游戏广场和指定游戏页。

| 项目 | 说明 |
| --- | --- |
| 文件路径（full） | sdk/tap-relation/.../extensions/SysExt.kt |
| 文件路径（lite） | sdk/tap-relation-lite/.../extensions/SysExt.kt |
| 方法 | goTapTap(targetUrl, targetUri, sessionId) / goGame(targetUri) |
| 目标包名检测 | getTapPkgName()：CN→com.taptap，Global→com.taptap.global |
| URI 来源 | 服务端下发的 goTapUri（客户端 Deeplink）或 goTapUrl（H5 地址） |
| Session 追踪 | appendSessionPlaceholder()：URL 追加 utm_sid={SID}，URI 追加 sess_id={SID} |
| Intent 构造 | ACTION_VIEW + setData(Uri.parse(result)) + FLAG_ACTIVITY_NEW_TASK |

**goTapTap 调用流程：**
1. isTapInstalled() 判断
2. 已安装 → 优先用 targetUri（Deeplink）；无 URI 则用 targetUrl；均为空则用服务端下发的默认 goTapUri
3. 未安装 → 用 targetUrl；为空则用服务端下发的默认 goTapUrl（H5）
4. 统一替换 {SID} 占位符后 startActivity

**goGame 调用流程：**
1. 直接用服务端下发的游戏 targetUri（Deeplink）
2. ACTION_VIEW 跳转
3. 异常时弹 Toast「跳转失败，请检查链接」

**特殊场景：**
tap-relation 和 tap-relation-lite 各自维护一份 SysExt.kt，逻辑完全一致，但依赖各自的 TapRelationInternal / TapRelationLiteInternal 实例获取服务端下发的默认跳转 URL。

---

## 公共能力：TapTap 安装检测与包名解析

多个模块共用同一套安装检测和包名解析逻辑，集中定义在 tap-common 模块。

| 项目 | 说明 |
| --- | --- |
| 文件路径 | sdk/tap-common/.../extensions/SysExt.kt |
| PACKAGE_NAME_CN | "com.taptap" |
| PACKAGE_NAME_GLOBAL | "com.taptap.global" |
| getTapPkgName() | 按 TapTapKit.regionType（CN / 非CN）返回对应包名 |
| isTapInstalled() | packageManager.getPackageInfo(getTapPkgName(), 0) 检测安装状态 |
| getTapVersionCode() | 获取已安装 TapTap 的 versionCode，用于版本兼容判断 |

> **注意：** tap-relation、tap-relation-lite 各自有本地副本的 getTapPkgName() / isTapInstalled()，与 tap-common 逻辑等价，但依赖各自模块的 region 字段。

---

以上为当前代码全量梳理，后续如有新增调用 TapTap 主站的交互点，请同步更新本文档。
