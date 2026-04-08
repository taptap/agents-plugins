# Android 三方交互外部影响评估

本模块在 change-analysis 工作流中**按需激活**：仅当待分析 MR 属于 **Android 项目**，且 diff 命中
[taptap-android-third-party-interaction-capabilities.md](taptap-android-third-party-interaction-capabilities.md)
中列出的高风险文件或交互模块时，才在 `code_change_analysis.md` 追加本章节，并在 `test_coverage_report.md`
中追加对应的测试访问评估和建议用例。

**参考资料说明**：

| 文档 | 视角 | 用途 |
| ---- | ---- | ---- |
| [taptap-android-third-party-interaction-capabilities.md](taptap-android-third-party-interaction-capabilities.md) | 主站侧 | **命中判断依据**：列出主站中哪些文件/代码块承接了外部 SDK 的调用，MR diff 对照此文件做匹配 |
| [taptap-sdk-android-to-main-app-calls.md](taptap-sdk-android-to-main-app-calls.md) | SDK 侧 | **兼容性分析参考**：描述 SDK 如何向主站发起调用，在撰写"受影响 SDK 模块"和"潜在断链场景"时按需查阅，不参与命中判断 |

---

## 命中判断规则

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

> **不命中则跳过本模块**，`code_change_analysis.md` 和 `test_coverage_report.md` 均不追加外部影响相关章节。

---

## 激活后操作流程

### 步骤 1：写入 `code_change_analysis.md` 外部影响评估章节

在阶段 4（impact）完成影响面分析后，追加以下章节到 `code_change_analysis.md`：

```markdown
## 八、外部影响评估（Android 三方交互）

> 本章节由 Android 三方交互命中检测自动激活，分析本次变更对外部 SDK / 游戏接入方的潜在影响。

### 8.1 命中交互模块汇总

| 交互模块 | 命中文件 | 风险等级 | 参考章节 |
| -------- | -------- | -------- | -------- |
| （按命中填写） | ... | ⚠️/🔶 | ... |

### 8.2 逐模块兼容性风险分析

> 对每个命中的交互模块，按以下格式分析：

#### {模块名称}（如：1.2 购买授权查询 / InAppBillingService AIDL）

**变更内容**：
- 简要描述本次 diff 中对该模块的具体改动（引用变更点编号或完整描述）

**影响分析**：
- **向前兼容性**：现有接入该接口的游戏 / SDK 是否仍可正常调用（是 / 否 / 需验证）
- **接口契约变化**：AIDL 方法签名 / Bundle key / Action 字符串 / resultCode / Extra key 是否发生变化
- **受影响 SDK 模块**：列出依赖该交互点的 SDK 模块（参考 `taptap-android-third-party-interaction-capabilities.md`）
- **潜在断链场景**：如有变更，描述哪些 SDK 调用路径会断链或异常

**置信度**：[已确认] / [基于 diff] / [推测]

**建议措施**：
- 是否需要 SDK 侧联动发版
- 是否需要灰度验证特定游戏
- 是否有协议冻结要求（如 AIDL 方法签名）

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
## 八、外部影响测试访问评估（Android 三方交互）

> 本章节随外部影响评估模块激活，提供针对三方交互变更的测试路径和建议用例。

### 8.1 测试访问路径说明

| 命中模块 | 测试访问方式 | 最低验证手段 |
| -------- | ------------ | ------------ |
| 1.1 SDK 登录授权 | 使用集成 TapSDK 的测试游戏执行登录流程 | 能正常返回 LoginResponse Bundle |
| 1.2 InAppBillingService AIDL | 通过 tap-license 测试 Demo 绑定 Service | AIDL 方法调用返回正确结果 |
| 1.3 CheckLicenseAct | 启动 CheckLicenseAct 并检查 onActivityResult | resultCode 和返回结构正确 |
| 1.4 DLC 内购 | 触发 DLC 购买流程 | DLC 内购弹窗正常显示，resultCode 正确 |
| 1.5 Scheme 路由 | 通过 adb shell am start 触发对应 Scheme | 能正常跳转到目标页面 |
| 1.6 图片分享 | 从外部 App 发起图片分享，选择 TapTap | 分享成功且发帖编辑器正常打开 |
| 1.7 防沉迷兼容 | 通过老版本 SDK Demo 绑定 AntiAddictionService | 调用 getUserAntiAddictionInfo 返回正常 |
| 1.8 SDK 初始化 | 使用 TapSDK Demo 执行完整初始化流程 | TapKit / OpenLog / GID 初始化无报错 |
| 2.1 JSBridge | 打开内嵌 H5 页面调用对应 action | JSBridge 响应正常，权限校验生效 |
| 2.2 悬浮球 JSBridge | 在游戏中打开悬浮球，触发 H5 功能 | login / getLoginCertificate 等 action 正常 |
| 3.1 沙盒 AIDL | 在沙盒内运行游戏并触发对应能力 | 账号检测 / 防沉迷 / 路由跳转正常 |
| 3.2 主站→沙盒 | 在沙盒游戏运行时触发用户信息同步 | setUserInfo / setGameInfo 等正常同步 |

> 仅列出本次**命中的模块行**，未命中的行删除。

### 8.2 建议测试用例

> 为每个命中模块生成不少于 1 条关键路径测试用例和 1 条边界/异常测试用例。
> 同时将这些用例写入 `supplementary_cases.json`（格式同本文件其他用例，tags 固定为 `["变更分析"]`）。

#### {命中模块名称} — 关键路径

- **优先级**：P0（⚠️ 高风险模块）/ P1（🔶 中风险模块）
- **前置条件**：
  - 使用集成对应 TapSDK 模块的测试游戏
  - 主站安装包为本次变更版本
- **步骤**：
  1. 操作：{发起调用，如 startActivityForResult / bindService / startActivity Scheme}
     预期结果：{正常返回 / 跳转成功 / 接口响应正确}
  2. 操作：{验证接口契约关键字段，如 Bundle key / resultCode / AIDL 方法返回值}
     预期结果：{字段值符合预期，未发生结构性变更}

#### {命中模块名称} — 兼容性边界

- **优先级**：P1
- **前置条件**：使用老版本 SDK（明确版本号）的测试游戏
- **步骤**：
  1. 操作：{以老版本 SDK 方式发起调用}
     预期结果：{主站能正常响应，不因新版本变更导致老版本断链}

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
| 阶段 3A：diff 分析 | MR 属于 Android 项目时，完成文件分类后执行命中检测 | 对照「命中判断规则」标记命中项，记录到 `change_checklist.md` |
| 阶段 4：impact | 追加 `code_change_analysis.md` 第八章 | 按「步骤 1」模板填写逐模块分析 |
| 阶段 6：generate | 追加 `test_coverage_report.md` 第八章 | 按「步骤 2」模板填写，并将新增用例同步写入 `supplementary_cases.json` |
| 阶段 7：output | `change_analysis.json` 的 `key_findings` 和 `action_items` 中体现外部影响条目 | 命中 ⚠️ 级别时补充外部影响高风险发现 |

> **不命中时**：上述所有介入点均跳过，不新增任何章节，不影响主工作流其他内容。
