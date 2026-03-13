<!--
  项目专属审查规则（Project Review Rules）

  本文件定义项目特有的代码审查规则，审查引擎会自动加载。
  如果没有填写任何规则（仅有注释），此文件不会影响审查结果。

  格式说明：
  每条规则是一个 ## 标题的 section，包含：
  - 标题 + 严重级别：## 规则名称 (BLOCKING/WARNING/NIT)
  - **scope**: glob pattern，匹配需要检查的文件路径（支持多行，每行一个 pattern）
  - 规则描述：具体检查什么
  - 合规示例 / 违规示例：帮助 reviewer 准确判断

  严重级别说明：
  - BLOCKING: 必须修复才能合并
  - WARNING: 建议修复，不阻塞合并
  - NIT: 风格建议，可忽略

  常见规则类型（按需添加）：
  - API 字段注释/文档要求（proto 注释、swagger 注解、KDoc/JavaDoc）
  - 命名约定（包名、类名、方法名规范）
  - 目录结构约定（新文件应放在哪里）
  - 依赖管理（禁止引入特定依赖、版本锁定）
  - 配置文件格式（特定 key 必须存在）
  - 国际化/本地化要求

  示例规则（取消注释并修改后生效）：

  ## API 字段注释 (BLOCKING)

  **scope**: `src/api/**/*.proto`

  所有 Request/Response message 及其引用的 model，每个字段必须有行尾注释说明含义。

  合规：
    string name = 1; // 用户昵称
  违规：
    string name = 1;

-->
