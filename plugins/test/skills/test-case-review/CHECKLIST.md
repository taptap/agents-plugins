# 用例评审检查项

本文件提供 `test-case-review` 在 `review` 阶段使用的检查项。SKILL.md 保留维度概览表，逐项检查时读取本文件。

4 维度详细检查项见 [共享评审框架](../_shared/REVIEW_4_DIMENSIONS.md)。

## 本 skill 补充说明

- 评审对象是外部提供的已有测试用例（非本流程生成），通过 RP-N 编号关联需求验证点
- 覆盖映射表按 RP-N 分组：RP-N → 用例列表 → 覆盖状态
- 评审结果输出到 `tc_review_detail.md`
- 评审框架与 test-case-generation 内置评审一致；本 skill 专注评审非 test-case-generation 流程生成的已有用例
