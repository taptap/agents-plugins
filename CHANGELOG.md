# Changelog

## 0.1.48

### Test Plugin (0.0.16)

**Code-review fixups (PR #61 third-round)**

- `test-case-generation/PHASES.md §2.4` rewritten as single-Agent multi-dimension strong-reasoning (functional / exception / user dimensions executed serially in main Agent context); removed all `Read agents/requirement-understanding/...` / `Task` calls that referenced the deleted perspective subagent files. Aligns with the §0.1.42 single-agent rewrite of `requirement-review` / `requirement-clarification`
- `_shared/AGENT_PROTOCOL.md` directory tree and naming convention list updated to drop the deleted `requirement-understanding/` directory; added a note explaining the consolidation
- `metersphere-sync/PHASES.md §4.0` smoke-test prelude now handles all five `verdict` enum values (`fail` / `fail-with-degraded-input` / `inconclusive` / `pass` / `pass-with-warnings`) rather than only `fail` vs `pass`. `fail-with-degraded-input` and `inconclusive` both trigger the same Prepare downgrade as `fail`; comment text now includes the actual verdict so reviewers can distinguish honest degraded fails from clean fails
- README and README.en updated: root插件表 test 0.0.10 → 0.0.16

## 0.1.47

### Test Plugin (0.0.15)

**`test-case-generation/contract.yaml` input/output 修订**

- `clarified_requirements` 和 `requirement_points` 从 `optional` 移到 `required`（两者成对出现，任一存在即可启动 session）
- 新增 `final_cases.json` 输出条目（output 阶段的最终用例集，对外可入库）
- `test_cases.json` 标 optional，描述改为 review 前快照，已被 `final_cases.json` 覆盖

## 0.1.46

### Test Plugin (0.0.14)

**Rename `shared-tools` → `test-shared-tools` (avoid cross-plugin name collision)**

- Skill name and directory renamed from `shared-tools` to `test-shared-tools`; the original name was too generic and risked colliding with downstream repos installing this plugin alongside other "shared tools" skills
- Synced all references across plugin docs (`README.md`, `CONTRACT_SPEC.md`, `AI_CODING_BEST_PRACTICES.md`), every consumer skill (`SKILL.md`/`PHASES.md`/`contract.yaml` for change-analysis, requirement-clarification/review/traceability, test-case-generation/review, metersphere-sync, api-contract-validation, qa-workflow), agent prompts (`case-tracer.md`, `codex-change-analyzer.md`), `_shared/TRACEABILITY_PROTOCOL.md`, `tests/validate.sh`, and `.pre-commit-config.yaml`
- No script-internal logic changes; only path/name updates so all `$SKILLS_ROOT/shared-tools/...` invocations now resolve as `$SKILLS_ROOT/test-shared-tools/...`

## 0.1.45

### Test Plugin (0.0.13)

**Smoke-test source 8 (SEARCH-A/B/C) for low input quality**

Empirical: GameJam case (session 253) recall 0/3 against QA-tracked P1/P2 bugs in low-input-quality mode; same input under new source 8 (session 254) recall 3/3.

- `requirement-traceability/PHASES.md §5S.1 source 8` — low-input-quality compensation searches (CRITICAL, fires only when `input_quality == "low"`):
  - **SEARCH-A**: new data-source coverage check (new tables/fields ↔ all read aggregation paths)
  - **SEARCH-B**: time-field boundary check (`StartTime`/`EndTime`/`ExpiresTime` ↔ consume/display paths missing `now ⋛ boundary` guard)
  - **SEARCH-C**: batch-operation bounds (for-range / batch SQL / loop-write ↔ `batch_size` / field-range / transaction boundaries)
- Execution constraint to avoid N×3 full-repo greps: classify diff hunks once into 3 buckets, then run each search once per bucket; grep scoped to diff-affected packages first, widen only on miss
- `contracts/defect-list.schema.json`: `evidence.search_id` added (string, pattern `^S[ABC]-\d+$`); `if/then` enforces `search_id` required when `evidence.source ∈ {search-a, search-b, search-c}` — verified with 6 fixtures (4 reject / 2 accept)
- Removed redundant "(注意是 X 不是 Y)" tails from `description`/`expected_result`/`actual_result` in TEMPLATES (TEMPLATES.md naming hard-constraints table is canonical)
- `TEMPLATES.md`: new defects naming hard-constraints table (`title→name`, `desc→description`, `expected→expected_result`, `actual→actual_result`) above defects example; defects example shows `evidence.source` enum including `search-a/b/c` and `search_id` field

## 0.1.44

### Test Plugin (0.0.12)

**MeterSphere helper: lazy credential check (CI-friendly)**

- `metersphere_helper.py` `_check_ms_credentials(cmd)` runs at `main()` dispatch time, before any subcommand handler. `validate-fv` (and any future local-only subcommand) skips the check via `_LOCAL_ONLY_COMMANDS` allowlist
- Allowlist is "local only" rather than "MS only" so future MS-bound subcommands inherit the check by default — safer than the inverse
- Replaces the prior `tests/validate.sh` workaround that wrapped Check N+2 with `MS_*` ci_dummy env exports (no longer needed since the helper now skips the check at root)

## 0.1.43

### Test Plugin (0.0.11)

**Smoke-test honest verdict + cross-component evidence completeness + ui-fidelity/api-contract consolidation**

GameJam-class漏报 root-cause fix (`input_quality` + supplementary cases routing) plus output-spec evidence completeness and architectural consolidation.

- **Smoke-test honest verdict**: `requirement-traceability/PHASES.md §1.3.d` introduces `input_quality` (full/medium/low) as single source of truth for all degradation behavior; §3.1 priority 1.5 tier consumes `change_supplementary_cases.json`; §4.6 fallback synthesis only when `input_quality=low` (non-low + empty fv → STOP, no more silent fallback masking); §5S.2 verdict expanded from binary to 5 tiers (`pass` / `fail` / `pass-with-degraded-input` / `fail-with-degraded-input` / `inconclusive`); §5S.1 supplementary defects inherit ca priority directly
- **Output-spec evidence completeness §3.2.0a**: A (data-flow closure) + B (cross-boundary recording) + D (path-driven failure modes) mechanically validated by `validate-fv`; C (per-expected reconciliation) is honest model self-check, NOT in validator (mechanical keyword match would create false safety); new `cross_component_break` defect source (5S.1 source 7); `forward_verification.schema` `requirement_id` pattern supports `FP-N | FP-UNMAPPED-N | R-N`; `case_source` enum added; `smoke-test-report.schema` `verdict` 5-tier + `input_quality` + `verification_channel` as required fields; `defect-list.schema` `P3` added for supplementary inheritance
- **ui-fidelity-check skill consolidated**: standalone skill removed; check exclusively triggered inside `requirement-traceability §3.4` via shared `ui-fidelity-checker` agent. `agents/api-contract-validator.md` (new) extracted from `api-contract-validation/PHASES.md §3` for stateless reuse
- **CI hardening**: new `tests/validate.sh` Check N+2 builds 4 synthetic fv entries (3 violations + 1 fail-path compliant) and asserts validator produces ≥1 of each A/B/D error class — regression-locks the validator behavior

## 0.1.42

### Test Plugin (0.0.10)

**requirement-review / requirement-clarification — single-agent strong-reasoning rewrite**

- Replaced multi-perspective subagent design with single-agent + structured reasoning across `requirement-review` and `requirement-clarification`; aligns with industry practice that single agent + strong schema + grounded reasoning beats parallel subagents for requirement-style analysis where context fits one window
- Removed three perspective subagent definitions (`agents/requirement-understanding/{user,functional,exception}-perspective.md`); only consumers were the two skills above, both refactored
- Promoted `requirement-review` 4.1b serial review to canonical path with mandatory 假设 / 反例搜索 / 结论 + original-text quoting
- Added `requirement-review` §4.1.7 enum normalization (anti-collapse) and §4.1.8 multi-variant consistency (class-inheritance defense against UI implicit propagation)
- Added `rr_summary.confidence` (0-100) with reproducible scoring formula in §5.1.5.1
- Replaced verdict OR rule with priority chain (hit-and-stop) so verdict is unique under any (confidence, blocking) combination — previously `confidence=50, 阻断=6` would land in both `not_ready` and `ready_with_conditions`
- Renamed mode wording from disparaging "degraded" to neutral "设计稿评审模式 / 描述评审模式" (review keeps 3 modes; no exploratory mode since Story context is required)

**Feishu report formatting — checkbox feedback loop**

- `requirement-review/TEMPLATES.md` §3 各职能问题列表改为 list + P0/P1 + 二选一 checkbox 反馈结构; added Closing Checklist Next Steps with handoffs to `test-case-generation`
- `test-case-review/TEMPLATES.md` §6 修复 to-do uses MeterSphere edit links + `[已修复/无需修复]` checkbox; rewrote todo lines to use action verbs (修步骤/补步骤/改预期 etc.) instead of internal dimension tags; converted §2 coverage matrix to tables
- `requirement-traceability/TEMPLATES.md` §4 缺陷清单 adds `[有效 bug/无效 bug]` checkbox per defect with `---` dividers; converted §3.1 coverage matrix and §3.2 code traceability to tables
- `change-analysis/TEMPLATES.md` converted §2.5 model fields, §4.1/§4.2 impact domains, §3 coverage to tables; added §6 cross-validation summary template with §6.4 综合结论 checkbox

**Conventions / shared / contracts**

- New `CONVENTIONS.md`「飞书文档渲染规范」section as the single source of truth on table-vs-bullet selection, banned elements, severity terminology; replaces obsolete "no markdown table" rule that lived in each skill (Feishu import has supported tables for some time, verified end-to-end)
- `_shared/REQUIREMENT_DIMENSIONS.md` terminology mapping table aligns severity (阻断/关注 with P0/P1 alias for `report.md`), status (per-FP vs per-dimension), and verdict↔confidence mapping; deprecates blocking/concern English and the 4-tier 阻断/高/中/低
- `contracts/rr-summary.schema.json` makes `confidence` and `blocking_issues` required (must be explicit empty array if none)
- `contracts/rr-summary.schema.json` fixture in `tests/check-schemas.sh` updated to include `confidence` plus out-of-range / missing rejection cases
- `requirement-clarification` redesigned single-agent confidence formula; aligned severity to Chinese 阻断/关注

**`AI_CODING_BEST_PRACTICES.md` — engineer-perspective rewrite**

- Added "按问题查" entry table at the top so half-flow readers can jump directly to the section they need (Quickstart / phase / troubleshooting / glossary / anti-patterns)
- New §0 Quickstart (5 steps to launch): plugin install command, `TEST_WORKSPACE` env setup, MS credential pointer, copy-paste first prompt, navigation hint
- Each phase gains a copy-paste prompt template (fillable variables) replacing the abstract "用 X skill 帮我..." phrasings
- Phase 3 walkthrough expanded with concrete plan-mode 三段式: design prompt template, review checklist (影响面 / 分步顺序 / 回滚成本) as a 3-row table with what-to-ask-AI and remediation, implementation discipline (compile per task)
- New 「反模式」 section with 6 anti-patterns; new Troubleshooting table (8 common failure modes); new 术语小词典 (11 entries)
- 进一步阅读 split into 必读 (5 entries) vs 选读 (5 entries); unified visual callouts (💡 原则 / ⚠️ 坑 / ✅ 产出 / 📥 输入)
- **Team-internal content moved to Feishu** (case study with internal ticket IDs, RACI assuming specific org structure, internal contacts) — repo doc points to Feishu supplement via single line; rationale: these don't generalize for an open marketplace plugin
- README ↔ AI_CODING_BEST_PRACTICES dedup: README scoped strictly to *catalog* (skills / how to pick / where files live / how to configure / version history); BP owns *task-driven SOP*. Dropped 6-step pipeline diagram and 链路 A data-flow box from README

**MeterSphere config — fixed misleading "zero-config" claim**

- `metersphere-sync/SKILL.md` and `AI_CODING_BEST_PRACTICES.md` previously claimed MS credentials were "built-in / zero-config / 已内置". This was false: `metersphere_helper.py` reads from `plugins/test/skills/shared-tools/scripts/.env`, and only `MS_DEFAULT_MAINTAINER` (admin) / `MS_DEFAULT_STAGE` (smoke) actually have built-in defaults. The other 11 `MS_*` vars cause runtime failures when missing
- Both docs now describe the actual lazy-path UX: don't pre-configure; on first run the script throws `missing required environment variables`, at which point user pastes the Feishu config block to the AI agent, which writes it into `.env`. Same end state as manual config but no upfront friction
- `metersphere-sync/SKILL.md` "环境变量" table expanded from 6 to 11 rows; 默认值 column corrected; added `MS_WORKSPACE_ID` and 4 `MS_FIELD_ID_*` rows that were missing
- `metersphere_helper.py`: lazy MS env credential check at `main()` dispatch time instead of module load. New `_LOCAL_ONLY_COMMANDS = {'validate-fv'}` whitelist lets pure local subcommands skip the check; everything else still fails early with the same `precondition_failed` payload. Allowlist is "local only" rather than "MS only" so future MS-bound subcommands inherit the check by default — safer than the inverse

**Smoke-test honest-verdict overhaul — close GameJam-class silent fallback**

Root cause discovered via forensic review of session 311/312 artifacts: when smoke-test ran without any test case input (no `final_cases.json` / `change_supplementary_cases.json` / `requirement_points.json`), it silently fell back to coverage-report synthesis (PHASES §4.6) and still emitted a hard `verdict: fail`. In one real case (GameJam project), change-analysis had already produced a supplementary case (`TC-11`) precisely targeting an Info-vs-Consume cross-path consistency bug, but smoke-test's input router never consumed it. This release introduces a single authoritative field `input_quality` (full/medium/low) and routes all downstream degradation behavior through it.

- `requirement-traceability/PHASES.md`:
  - **§3.1**: input router now has 4 priority tiers; new tier 1.5 consumes `change_supplementary_cases.json`. Cases inherit ca's `case_id` (`TC-{N}`). `module` reverse-lookups `traceability_checklist.md` for `requirement_id`; falls back to `FP-UNMAPPED-{N}`. Each derived fv entry tagged `case_source: "supplementary"` for §5S.1 priority inheritance
  - **§1.3**: applies in all modes (smoke-test no longer skips entire 1.3); only the `mapping_sha` check is mode-gated. New §1.3.d "case input integrity check" sets `input_quality` and writes `_input_quality.json` for downstream consumption
  - **§3.1.5**: enum_coverage_gap now exempts gaps covered by supplementary cases — prevents real fail from being downgraded to inconclusive when ca had filled the gap
  - **§4.4**: `traceability_coverage_report.json` now writes `input_quality` and `verification_channel`. The latter is auto-computed from fv content — model is no longer free to label it `dual_channel` for cosmetic reasons
  - **§4.5**: `risk_assessment.json` confidence cap when `input_quality == "low"` (60) or `medium` (80); standard mode now also gets honest degradation, not just smoke-test
  - **§4.6**: bottom-out synthesis only triggers when `input_quality == "low"`. If fv is empty but `input_quality != "low"` → STOP and surface "§3.2 has a bug, don't mask via fallback" — eliminates the silent-bypass class entirely
  - **§5S.1**: new priority inheritance for supplementary cases — directly inherits ca's `priority` (P0/P1/P2/P3) instead of confidence-based bumping. GameJam TC-11 P0 now correctly enters defect_list
  - **§5S.2**: verdict expanded from binary (pass/fail) to five-tier table by `input_quality × P0 count`: `pass` / `fail` / `pass-with-degraded-input` / `fail-with-degraded-input` / `inconclusive`. Engine refuses hard verdict on degraded input
- `_shared/schemas/forward_verification.schema.json`: `requirement_id.pattern` relaxed to `^(FP-\d+|FP-UNMAPPED-\d+)$`; new optional `case_source` enum field
- `contracts/smoke-test-report.schema.json`: `verdict.enum` expanded to five values; new `input_quality` and `verification_channel` enums. **Downstream impact**: ai-case backend's frontend mapping needs to handle the 3 new verdict values

**Output-spec evidence completeness (A/B/D enforced + C self-check), cross-component data flow tracing**

Continuation of the GameJam fix — even when supplementary cases ARE consumed, single-component追溯 still misses cross-end data flow bugs (frontend↔backend, admin↔C-end, read-path↔write-path). The fix is **output-spec validation, not process-spec prompts**: the model picks any tracing strategy, but produced evidence must satisfy 4 completeness constraints, A/B/D validated mechanically.

- `requirement-traceability/PHASES.md §3.2.0a (NEW)`: Evidence completeness contract. (A) Data-flow closure: pass + conf>=70 trace must contain ≥1 → / -> (≥2 hops). (B) Cross-boundary natural recording: pass + conf>=85 + multi-actor trace → code_location ≥2 entries distributed across ≥2 directory roots. (C) Per-expected reconciliation: model self-check (validator does NOT mechanically check — keyword match would create false safety). (D) considered_failure_modes path-driven: trace contains grpc/cache/transaction/async/state-mgmt/db patterns → modes must contain matching keywords
- `_shared/scripts/metersphere_helper.py validate-fv`: implements A/B/D mechanical checks. `_validate_completeness()` runs after schema + boundary checks. Synthesized entries (4.6 fallback) skip A/B/D as schema already exempts their evidence. Each violation produces `schema_path: completeness/{A|B|D}` with case_id and structured fix hint
- `requirement-traceability/PHASES.md §5S.1 source 7 (NEW)`: cross_component_break defect source. (7a) Trace covers ≥2 components but a hop has no implementation in diff → P0 if hop touches data contract (read/write asymmetry like GameJam Info-Consume), P1 otherwise. (7b) FE↔BE field semantic divergence
- `contracts/defect-list.schema.json`: documented `cross_component_break` as new category value (additive — schema is permissive on category)
- `tests/validate.sh`: new Check N+2 builds 4 synthetic fv entries (3 violations + 1 fail-path compliant) and asserts validator produces ≥1 of each A/B/D error class. Regression-locks the validator behavior

**ui-fidelity-check skill removed; UI/API checks consolidated into traceability via shared agents**

- `plugins/test/skills/ui-fidelity-check/` directory removed entirely. UI fidelity check is now exclusively triggered inside `requirement-traceability §3.4`. Rationale: TapTap multi-platform stack rarely has a deployed `page_url` available — most scenarios are static code + design draft. Removing the page_url path and unifying on structural-only mode covers all platforms / all dev phases. With page_url gone, ui-fidelity-check and traceability §3.4 became truly equivalent (same agent, same input, same output) → standalone skill no longer justified
- `agents/ui-fidelity-checker.md` retained and simplified: dropped Browser MCP inputs; now compares Figma structured design data vs static code style declarations only (CSS / SCSS / Tailwind / SwiftUI Modifiers / Compose Modifiers). Confidence cap 60 (no runtime validation)
- `agents/api-contract-validator.md` (new): extracted from `api-contract-validation/PHASES.md §3` (signature extraction + 4-dim cross-comparison + breaking change + naming normalization). Stateless calc unit, returns findings JSON. `api-contract-validation` skill **kept** as standalone entry; `requirement-traceability §3.2.5` rewritten to launch the same agent. Upstream-first kept as performance optimization (if `api_contract_report.json` exists in workspace, skip agent launch)
- Why ui-fidelity deleted but api-contract kept: ui-fidelity has identical user job in both entries (need design + code); api-contract serves a distinct user job (no requirement, just FE↔BE diff) → standalone skill preserves a real entry point. AI agent skill selection benefits from distinct skill descriptions
- Cascade cleanup: `qa-workflow` step #6 removed (renumbered downstream steps); `WORKFLOW_DEFS.md` qa-full / qa-lite / verify-only templates updated; `PIPELINES.md` 链路 D rewritten; `known-collisions.yaml` ui_fidelity_report entry deleted; `_shared/TRACEABILITY_PROTOCOL.md` UI section rewritten
- `traceability/contract.yaml`: added `code_dir` input; removed `ui_fidelity_report` upstream input + `from_upstream: ui-fidelity-check`

### Marketplace

- Bumped version from 0.1.41 to 0.1.42
- Updated test plugin to version 0.0.10

## 0.1.41

### Test Plugin (0.0.9)

**requirement-review**

- Optimized 10 readability issues in Feishu reports based on real samples; rebuilt `TEMPLATES.md` for `report.md`
- Fixed 5 Feishu docx import compatibility issues + 4 structural issues (TOC, section numbering, intent table, chat output) after live import testing
- Fixed `rr_summary.json` writing illegal `review_mode` values like `single_agent_serial` (schema enum is now enforced)

**test-case-review**

- Added `TEMPLATES.md` (8-section strict template for `review_summary.md`); previously had no report template
- Added §0 case-readiness verdict and §6 fix to-dos grouped by case ID (bold ID + `· ` prefix to preserve hierarchy after Feishu flattens nested bullets)

**change-analysis**

- Added `TEMPLATES.md` constraining multi-doc Feishu output (`code_change_analysis.md` + `test_coverage_report.md`); introduced bidirectional cross-references and per-line `[实证]/[推测]` confidence tagging

**requirement-traceability**

- Added smoke-test mode `report.md` template (6 sections); previously PHASES 5S.2 only constrained JSON output, no markdown template
- Added §0 overall confidence summary + §2 numerator/denominator titles + §3.2 explicit untraced changes
- Fixed broken anchor `#coverage_reportjson` → `#traceability_coverage_reportjson` in PHASES.md

**Skill audit phase 1-3 follow-ups (8-dimension cross-skill review)**

- Bound `testcase.schema.json` on 5 `*_cases.json` output declarations across `test-case-generation` / `test-case-review` / `change-analysis` `contract.yaml` (was implicit via CONVENTIONS.md inheritance; now machine-checkable)
- Added demand-driven vs change-driven gating in `test-case-generation` and `change-analysis` SKILL descriptions + reverse SKIP cross-references between `change-analysis` and `requirement-traceability`
- Marked `review_result.json` as LLM-friendly non-strict JSON in `test-case-review/SKILL.md` (verdict object, not `TestCaseList`; deliberately not schema-bound)
- Synced `testcase.schema.json` from ai-case Pydantic source: `Step.expected` is now required (allows empty string); previously had `default=''` so callers could omit it. MCP tool input_schema auto-reflects this constraint at LLM tool-call time
- Relaxed `test_method` from required to optional in `CONVENTIONS.md` to match Pydantic (which was already Optional; documentation was lagging) — supplementary case producers may omit it
- Cross-referenced `contracts/known-collisions.yaml` from `requirement-traceability/PHASES.md` Phase 6 and `PIPELINES.md` to clarify that trace Phase 6 writeback and `metersphere-sync mode=execute` share the same `metersphere_helper.py writeback-from-fv` helper as two coexisting entry points (auto vs manual mode), not duplicate implementations
- Added `re_entry_phase` + `requirement_change_summary` optional inputs to `qa-workflow` for "rerun after requirement change" scenarios, passthrough to `test-case-generation`
- Updated README selection guide to surface the demand-driven (tcg) vs change-driven (ca) split; dropped stale "v0.0.10+" version gates from architecture features section
- Added quickstart note in `requirement-clarification/SKILL.md` clarifying that `output/*.json` files are pre-shipped format samples, not runtime artifacts
- Added inline annotation in `agents/` tree (README + `_shared/AGENT_PROTOCOL.md`) explaining why files in `plugins/test/agents/` are not auto-registered as Claude/Codex subagents (no YAML frontmatter; loaded explicitly via Task tool calls inside skills)

**Test plugin audit + CI hardening**

- Extended `tests/validate.sh` from 5 to 9 check categories: SKILL frontmatter ↔ directory, handoffs targets, subagent_type targets, references/ paths, contract.yaml cross-skill consistency
- Resolved 8 contract output collisions: renamed `risk_assessment.json` → `bug_risk_assessment.json` (change-analysis), split `test_execution_report.json` → `unit_/integration_test_execution_report.json`, split `supplementary_cases.json` → `change_/review_supplementary_cases.json` (canonical kept by test-case-generation)
- Added `contracts/known-collisions.yaml` whitelist with self-binding "review protocol" rule
- Removed 3 zombie agents (`forward-tracer`, `reverse-tracer`, `failure-classifier`) and cleaned up 13 dead references across SKILL/PHASES/TEMPLATES/protocol files
- Honest dependencies: `shared-tools/requirements.txt` now lists actual deps (pycryptodome, pyyaml, jsonschema, python-dotenv, aiohttp); new `feedback/requirements.txt` declares aiohttp; `feedback/contract.yaml` env_vars now match scripts (`FEISHU_PLUGIN_ID/SECRET/USER_KEY`)
- Standardized `-h/--help` UX across 5 shared helper scripts (previously `--help` was sent as a network query in `search_mrs.py`)
- Extracted `integration-test-design` 5-phase content into standalone `PHASES.md` (SKILL.md trimmed 387 → 252 lines, aligned with unit-test-design style)
- Schema validation expanded from 1 to 5 schemas (testcase / ca-summary / defect-list / rr-summary / smoke-test-report) with ~30 negative cases
- Synced stale filename references across PIPELINES.md (8), README.md (7), test-case-review/TEMPLATES.md (2), change-analysis/TEMPLATES.md (2), change-analysis/contract.yaml (1) following the contract renames above

### Marketplace

- Bumped version from 0.1.40 to 0.1.41
- Updated test plugin to version 0.0.9

## 0.1.40

### Test Plugin (0.0.8)

**requirement-clarification**

- Added 多变体一致性追问 (CRITICAL): when a requirement adds UI elements / modifies component behavior on cells/lists/tabs, or touches multi-tab pages, the skill must proactively ask whether the change applies to all variants — defends against class-inheritance / parent-component implicit propagation (e.g. "发出的 tab 错错展示了不再通知按钮" class of bugs)
- Added PRD doc-quality proofreading: surfaces missing acceptance criteria, undefined enums, ambiguous "等等" wording before clarification proceeds
- Added icon source confirmation: requires PM to specify icon source (设计稿原图 / 现有 icon library / 待补) instead of letting the agent guess
- Changed categorical-variable elicitation to force positive enumeration over exception phrasing (e.g. "支持 A/B/C" not "除了 D 都支持")
- Added enum_factors wiring through `requirement_points.json` so lite-pipeline downstream consumers preserve the enum coverage chain

**test-case-generation**

- Added phase 3.5 `scan-ambiguities`: between decompose and generate, the main agent enumerates `(functional_point, ambiguity)` pairs (unspecified expected behavior, missing boundaries, ambiguous branches), batches them into a single `AskUserQuestion`, writes results to `clarifications.json`. Generate consumes that file: confirmed answers fill `expected`; pending items force the step's `expected` to `[待确认] {原因}` so the writer cannot fabricate plausible-but-unspecified expectations
- Changed phase 6 `confirm` to skip review findings whose affected case already carries a `[待确认]` marker on the same step, preventing duplicate prompts
- Fixed forbid ambiguous OR in test case preconditions/steps/expected — agents now reject "A 或 B" phrasing during generation review
- Changed `test-case-writer` agent: added `clarifications.json` as a conditional input with explicit confirmed/pending handling rules

**requirement-traceability**

- Added Phase 4.6 forward_verification.json fallback synthesis: when Phase 3.2 doesn't produce per-case verification, synthesize from `traceability_coverage_report.json` per-FP verdict so MS testplan writeback always has fuel
- Changed Phase 6.1 to forbid silent skipping when `forward_verification.json` is missing — falls back to 4.6 synthesis or fails loudly
- Changed Closing Checklist to mark `forward_verification.json` and `ms_sync_report.json` as mandatory artifacts; explicitly forbids "degraded path" as an excuse to skip
- Fixed traceability ↔ metersphere-sync writeback chain (P10/P11/P12 from second TAP-6841255319 run): real Skill invocation, max_loop_iterations contract, plan_name resolution
- Closed D1-D12 dead branches in the traceability flow (mode dispatch, ID system, agent filenames, schema consistency)
- Extracted Recovery Cookbook from main PHASES.md into a standalone reference
- Deprecated forward-tracer (rolled into main agent path), updated description to be triggering-friendly

**integration-test-design**

- Added "集成测试价值评估" section: defines which scenarios deserve integration tests (API contracts, routing, cross-module notifications, telemetry payloads, auth gates, DB CRUD with side effects) vs which should be pushed to unit (pure deserialization, decision logic, state operations) or E2E (UI rendering, telemetry trigger conditions, pure passthrough)
- Changed analyze phase to require explicit layering judgement per scenario; non-integration scenarios now go to a "跳过的场景" table instead of being silently dropped
- Added shared `_shared/UNIT_VS_INTEGRATION_BOUNDARIES.md`: cross-skill boundary rules across `unit-test-design`, `integration-test-design`, `test-case-generation` (E2E), with L1-L6 layer ownership table and a one-line decision rule

**Docs (AI_CODING_BEST_PRACTICES.md)**

- Restructured into three reader-intent layers (30s lookup → per-stage SOP → case study); dissolved standalone "3 things to know" section into per-stage gotchas; dropped duplicate "what skill do I use" tables
- Stage 4 split into 4a (AI fidelity via `requirement-traceability`) and 4b (manual on-device walkthrough); multi-layer verification table now anchors each layer to a stage
- Stage 5 explicitly references git plugin coverage (`git:commit-push-pr`, `git:code-reviewing`)
- Stage 3 documents plan-mode three-phase flow (design → review → implement)

**feedback skill (chore)**

- Reassigned ownership of iOS 社区版 (wangweidong → jinshichen)
- Reassigned 易页's PM modules (聊天/好友/通知/账号 等) to 裘达立
- Reassigned 内容发布 dev contacts to 陈昊/刘峰/陈一豪

### Marketplace

- Bumped version from 0.1.39 to 0.1.40
- Updated test plugin to version 0.0.8

## 0.1.39

### Sync Plugin (0.1.30)

- Changed `hooks-config` agent: hooks scripts now sync to the project directory (`{PROJECT_ROOT}/.claude/hooks/`, `{PROJECT_ROOT}/.codex/hooks/`) instead of `~/.claude/hooks/`; copying is always force-refreshed so downstream repos pick up the latest scripts on every `/sync:hooks` or `/sync:basic` run
- Changed `ensure-codex-plugins.sh` to perform three steps: (1) self-heal the remote marketplace — detects stale local-clone sources, wrong origins, and broken clones, then re-registers via `codex plugin marketplace add taptap/agents-plugins` (compatible with both old `codex marketplace add` syntax and new); (2) mirror project-level enabled plugins to `~/.codex/config.toml`, preserving explicit user `enabled = false`; (3) auto-install cache for enabled plugins from the marketplace clone, with `INSTALLED_BY_DEFAULT` plugins auto-enabled when the user has not explicitly opted out
- Updated `codex-plugins-config` agent to document the force-refresh requirement for script copying (target file existence must not skip the copy)
- Updated `commands/basic.md` and `commands/hooks.md` to reflect project-level hooks sync and mandatory `ensure-codex-plugins.sh` refresh
- Updated sync plugin README: design-constraints section now describes the remote-marketplace self-healing architecture; removed obsolete local skills-mirror references
- Changed `tests/validate.sh`: significantly expanded `ensure-codex-plugins.sh` test coverage — added `create_fake_codex_plugin` / `create_fake_codex_marketplace_clone` helpers; added test cases for old-local-source self-heal, wrong-origin self-heal, Step 3 cache installation, and `INSTALLED_BY_DEFAULT` auto-enable logic

### Marketplace

- Bumped version from 0.1.38 to 0.1.39
- Updated sync plugin to version 0.1.30

## 0.1.38

### Test Plugin (0.0.7)

- Added `mcp__cases__save_test_cases` in-process MCP tool path for all `*_cases.json` writes: schema is built from backend `case_schema.TestCase` (Pydantic v2) via `TypeAdapter`, enforced at the Anthropic API generation layer so field-name typos and structural drift are rejected before the tool call lands; `Write *_cases.json` now denied by hook and redirected to the new tool
- Changed change-analysis, test-case-generation, test-case-review PHASES.md to instruct the model to call `mcp__cases__save_test_cases` instead of `Write`; Bash-merge escape retained for >50-case files (`test_cases.json`, `final_cases.json`) where pure LLM output paths risk token truncation
- Changed test-case-writer agent: removed `Write` from `tools`, added `mcp__cases__save_test_cases`; removed self-check section since schema is now enforced at generation
- Changed CONVENTIONS.md "严格校验" section to reflect the new layered defense (input_schema → tool-side `validate_cases` → hook redirect) instead of the obsolete PreToolUse hook narrative
- Changed test-case-generation PHASES.md to drop "post_complete 自动修正/兜底" framing in favor of "schema enforced at generation"
- Changed `_shared/LARGE_FILE_HANDLING.md` to clarify that MCP tool input is subject to the same LLM token limit as Write
- Fixed requirement-review degraded mode: allow review to proceed when requirement doc is missing instead of hard-blocking

### Marketplace

- Bumped version from 0.1.37 to 0.1.38
- Updated test plugin to version 0.0.7

## 0.1.37 — Codex plugins: zero-touch auto-install for team distribution

### Sync Plugin (0.1.29)

- Added Step 3 to `ensure-codex-plugins.sh`: auto-install enabled `*@taptap-plugins` plugins from the marketplace clone (`~/.codex/.tmp/marketplaces/taptap-plugins/`) into `~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/`. This is the equivalent of the TUI "Install plugin" action, which Codex 0.121.0 otherwise requires the user to run by hand for git-source marketplaces.
- The script now also auto-enables every plugin marked `INSTALLED_BY_DEFAULT` in `marketplace.json` (currently `git` and `sync`), unless the user has explicitly set `enabled = false`. Together with the project-mirror step, a fresh team member running the SessionStart hook gets `git`/`sync` registered, enabled, and installed end-to-end with zero TUI clicks.
- Reverse-engineered finding documented in the script header: `installed_plugins.json` is no longer used by Codex 0.121.0+; install state is derived from cache directory existence (`cache/<marketplace>/<plugin>/<version>/.codex-plugin/plugin.json`).

### Marketplace

- Bumped version from 0.1.36 to 0.1.37.
- Updated sync plugin to 0.1.29.

## 0.1.36 — Codex plugins: align with official `codex marketplace add` workflow + harness AGENTS.md

### Sync Plugin (0.1.28)

- Rewrote `ensure-codex-plugins.sh` to delegate cache management to Codex itself: the script now only registers `taptap-plugins` via `codex marketplace add taptap/agents-plugins` (when missing) and mirrors project-level `[plugins."*@taptap-plugins"] enabled = true` into `~/.codex/config.toml`. Removed all hand-rolled cache symlink and `installed_plugins.json` maintenance.
- Updated `codex-plugins-config` agent to document the new flow (GitHub remote registration, no local cache writes) and removed stale `~/.agents/plugins/` references.
- Replaced one validate.sh case with four new ones covering the new behavior (marketplace add when missing, skip when registered, project mirror, graceful skip when codex CLI is unavailable). Added schema validation that every `.codex-plugin/plugin.json` must include `interface.{displayName, category, capabilities}` and that `.agents/plugins/marketplace.json` matches `plugins/*/.codex-plugin/`.

### Git Plugin (0.1.16)

- Added required Codex `interface` block (displayName, shortDescription, longDescription, developerName, category, capabilities) so the plugin appears in the Codex TUI picker.

### Spec Plugin (0.1.8)

- Added required Codex `interface` block.

### Test Plugin (0.0.6)

- Added required Codex `interface` block.

### Repo harness

- Rewrote root `AGENTS.md` (also exposed as `CLAUDE.md` via symlink) into a proper harness file with sections for repository layout, commands, conventions, plugin contract, and safety rules. Codex now picks up the same instructions Claude Code already loaded.

### Marketplace

- Added `.agents/plugins/marketplace.json` (Codex-format) so `codex marketplace add taptap/agents-plugins` can discover the marketplace from GitHub. Each plugin declares `policy.installation`; `git` and `sync` use `INSTALLED_BY_DEFAULT` so adding the marketplace auto-installs the core plugins.
- Removed the blanket `/.agents/plugins/` ignore in `.gitignore` since Codex 0.121.0 does not write any artifacts under that directory.
- Bumped marketplace metadata version from 0.1.35 to 0.1.36.
- Updated git plugin to 0.1.16, spec plugin to 0.1.8, sync plugin to 0.1.28, test plugin to 0.0.6.

## 0.1.35 — Test plugin major refactor: traceability auto-writeback, handoff pilot, cross-repo contract bridge

### Test Plugin (0.0.5)

- Added requirement-clarification handoff pilot: frontmatter declares `handoffs[]` (recommended next skill, when, prompt hint); Closing step now emits a structured "Next Steps" block with copyable Skill() invocation and explicit confirm-to-relay prompt (spec-kit-style pattern, validated on a single skill before broader rollout)
- Added Phase 6 writeback in requirement-traceability: standard mode now invokes metersphere-sync execute internally to write back MS test plan case status, so running traceability standalone (outside qa-workflow) no longer leaves MS plans empty; smoke-test mode still skips MS write
- Changed qa-workflow to drop the standalone metersphere-sync execute step (#9 removed) since write-back is now handled by traceability; qa-full step IDs renumbered (#10/#11/#12 → #9/#10/#11); qa-lite/verify-only template skip lists updated; PHASES.md cross-references and earlier numbering inconsistencies fixed
- Removed `verification-test-generation` skill (and `agents/verification-test-writer.md`); merged its core capability into requirement-traceability's forward channel as embedded 3.2.0 traceability assessment + 3.2.1 tracing flow steps; retired the `verification_cases.json` intermediate artifact
- Changed requirement-traceability forward channel: now consumes `final_cases.json` directly (priority 1) → `requirement_points.json` acceptance_criteria (priority 2) → traceability_checklist.md descriptions (weakest); writes upstream `case_id` directly into `forward_verification.json` so MS write-back can match at test-case granularity (FP-level aggregation only in degraded mode)
- Changed `_shared/TRACEABILITY_PROTOCOL.md` artifact spec from "verification cases JSON format" to "forward_verification.json format" with updated field schema; CONVENTIONS.md numbering prefix table removed `VC-`
- Added cross-repo contract bridge with ai-case backend: `scripts/contract-bridge-check.py` validates skill contract.yaml output declarations against backend consumer references; rr_summary.json / ca_summary.json now declared in producer contracts
- Added 4 JSON schemas under `contracts/`: testcase.schema.json (auto-derived from ai-case Pydantic), defect-list.schema.json (catches field name drift), smoke-test-report.schema.json (catches verdict/summary drift), rr-summary.schema.json, ca-summary.schema.json
- Added codex_agent.py (`shared-tools/scripts/`): standalone OpenAI Chat Completions + Tool Use agent loop for Codex cross-validation when codex CLI unavailable; supports bash/read_file/grep tools with sandboxed work_dir
- Added codex-change-analyzer agent in change-analysis Phase 3.5 for parallel cross-validation analysis with environment-aware fallback (codex CLI → codex_agent.py → claude-fallback)
- Added contract-driven RR/CA summary outputs in test-case-generation: skill produces rr_summary.json / ca_summary.json with structured fields consumed by ai-case workflows
- Added strict case JSON schema enforcement across MS import path: rejects AI-written `tags` field (assigned by backend per workflow type)
- Added exploratory testing method as the 7th test method in test-case-generation, CONVENTIONS.md, and test-case-writer agent
- Added `_shared/TEST_QUALITY_GUIDELINES.md` to deduplicate rules across unit-test-design and integration-test-design
- Added `_shared/LARGE_FILE_HANDLING.md` to prevent JSON truncation in Write tool
- Added Closing Checklists to metersphere-sync, qa-workflow, requirement-review, and other skills
- Added negative trigger boundaries to reduce AI mis-triggering across skills
- Added requirement-review skill with 12-dimension evaluation framework
- Added change-analysis, test-case-review, and api-contract-validation skills
- Added smoke-test mode with defect extraction and P0 gate to requirement-traceability
- Added Android third-party interaction impact assessment to change-analysis
- Added data sufficiency gate for conditional report sections
- Changed feedback skill: split 800+ line monolith into SKILL.md + PHASES.md + TEMPLATES.md + TEAM_ASSIGNMENTS.md + contract.yaml
- Changed SKILL.md boilerplate: slimmed docs, split METHODS, improved triggers
- Changed intermediate file naming for disambiguation and shared content extraction
- Fixed feedback TEAM_ASSIGNMENTS.md: unified TapPlay dev owner to 陆航 (was contradicting across 3 locations)
- Fixed feishu_api.py `_request` method: corrected X-PLUGIN-TOKEN headers indentation into else block
- Fixed test case JSON format contract: eliminated Format A/B ambiguity
- Fixed confidence scoring contradictions in requirement-traceability
- Fixed large file write guard to prevent JSON truncation in test-case-generation
- Changed metersphere_helper.py: added `--tags` CLI parameter for per-workflow tag assignment
- Changed Feishu export: removed per-skill create_feishu_doc.py invocations, delegated to platform handler
- Fixed codex_agent.py path traversal: replaced `startswith` check with `Path.is_relative_to` to block sibling-prefix bypass (e.g. `/tmp/foo` vs `/tmp/foobar/x`)
- Fixed codex_agent.py OpenAI call timeout: floored to 5s to avoid passing 0/negative values to SDK when `elapsed` approaches budget
- Fixed feedback TEAM_ASSIGNMENTS.md: unified TapPlay dev owner to 陆航 (was contradicting across 3 locations)
- Fixed feishu_api.py `_request` method: corrected X-PLUGIN-TOKEN headers indentation into else block
- Fixed test case JSON format contract: eliminated Format A/B ambiguity
- Fixed confidence scoring contradictions in requirement-traceability
- Fixed large file write guard to prevent JSON truncation in test-case-generation
- Cleaned up deprecated bug-fix-review skill (merged into change-analysis)
- Cleaned up committed __pycache__ and added gitignore rule
- Untracked ai-workflow-panorama.html from version control

### Spec Plugin (0.1.7)

- Cleaned up ruff lint warnings in `doc-auto-sync` scripts (check-docs.py, check-stale-docs.py): removed unused imports, modernized type hints, no behavioral changes

### Marketplace

- Bumped version from 0.1.34 to 0.1.35
- Updated test plugin to version 0.0.5
- Updated spec plugin to version 0.1.7

## 0.1.33 — Add metersphere-sync, feedback skill, and Urhox binary analysis to test plugin

### Test Plugin (0.0.3)

- Added metersphere-sync skill for test plan management and case import with hierarchical module support
- Added qa-workflow orchestrator skill for end-to-end QA pipeline execution
- Added feedback skill: analyze Slack #taptap-feedback channel user feedback, classify issues, and create Feishu Bug tickets
- Added feedback skill knowledge base (10 reference docs: TapSDK, 实名, 下载安装, 评分, 配置, 内容发布, 注册登录, 青少年, 缺陷提交规范, 商店线产品分工)
- Added feedback skill Feishu API script for creating and updating Bug work items
- Added Urhox binary diff scope filtering to change-analysis phase 2.3
- Added Urhox binary impact analysis in change-analysis phase 3A
- Added test-case-generation sufficiency gate and iterative re-entry
- Added unified .env-based config for all Python scripts via python-dotenv
- Added requirement-clarification native AskUserQuestion tool calls
- Added phase execution guarantees and output validation for all multi-phase skills

### Marketplace

- Bumped version from 0.1.32 to 0.1.33
- Updated test plugin to version 0.0.3

## 0.1.32 — Add Codex plugin support and migrate marketplace repo name

### Sync Plugin (0.1.27)

- Added Codex plugin support with `.codex-plugin/` directory and manifest
- Added `codex-plugins-config` agent for configuring Codex plugins via standalone clone
- Added `ensure-codex-plugins.sh` and `update-codex-plugins.sh` scripts for Codex plugin auto-update
- Updated `/sync:hooks` command to include Codex hooks setup step (`.codex/hooks/` sync)
- Updated `/sync:basic` command to add Codex plugin standalone clone as Phase 1 step
- Updated `/sync:basic` and `/sync:lsp` project settings handling to migrate `taptap/claude-plugins-marketplace` to `taptap/agents-plugins` without overwriting custom repos
- Updated sync commands to prefer `${CLAUDE_PLUGIN_ROOT}` before installed marketplace/cache paths, so inline `--plugin-dir` development sessions resolve the current plugin source correctly
- Updated `ensure-plugins.sh` to migrate old marketplace repo name with robust jq-based detection
- Updated `set-auto-update-plugins.sh` to handle old repo name migration and add JSON validity check before parsing
- Updated `ensure-cli-tools.sh` to add shell-aware token setup hints (zsh/bash/fish)
- Simplified `hooks-config` agent to non-destructive project hooks check only; removed `permissionMode: acceptEdits`

### Git Plugin (0.1.15)

- Added `.codex-plugin/` manifest for Codex CLI compatibility

### Spec Plugin (0.1.6)

- Added `.codex-plugin/` manifest for Codex CLI compatibility

### Test Plugin (0.0.2)

- Added `.codex-plugin/` manifest for Codex CLI compatibility

### Marketplace

- Bumped version from 0.1.31 to 0.1.32
- Updated sync plugin to version 0.1.27
- Updated git plugin to version 0.1.15
- Updated spec plugin to version 0.1.6
- Updated test plugin to version 0.0.2

## 0.1.31 — Simplify sync workflow and remove Cursor-side distribution

### Sync Plugin (0.1.26)

- Removed Cursor-specific commands, templates, and snippet mirroring assets from the sync plugin
- Changed `/sync:basic` and related MCP commands to focus on Claude Code environment setup only
- Removed the `ensure-codex-skills.sh` SessionStart hook and stopped sync from maintaining `~/.agents/skills` for Codex
- Removed deprecated `sequential-thinking` MCP cleanup logic from mcp command, agent, and scripts
- Updated sync documentation, status checks, and helper skills to match the reduced Claude Code scope
- Cleaned up repo-local optional hook guidance after removing the bundled snippet sync pre-commit flow
- Added BASE subdirectory variable mapping documentation to `/sync:basic` command

### Marketplace

- Bumped version from 0.1.30 to 0.1.31
- Updated sync plugin to version 0.1.26

## 0.1.30 — Add QA workflow plugin with multi-agent test skills

### Test Plugin (0.0.1)

- Added QA workflow plugin with full test lifecycle skills
- Added test-case-generation skill with multi-agent review pipeline (dual reviewer + redundancy audit)
- Added unit-test-design skill with business-scenario-driven principles and language-specific methods (Go/Java/Kotlin/Python/Swift/TypeScript)
- Added integration-test-design skill with framework-specific methods
- Added verification-test-generation skill for code-level test generation with phase execution guarantees
- Added change-analysis skill with Android third-party interaction impact assessment
- Added requirement-clarification skill with structured Q&A cards and ask_question output format
- Added requirement-review skill with 12-dimension evaluation framework
- Added requirement-traceability skill with smoke-test mode, defect extraction, and P0 gate
- Added test-case-review skill with 4-dimension review protocol
- Added api-contract-validation skill with contract enforcement
- Added bug-fix-review and test-failure-analyzer skills
- Added ui-fidelity-check skill with Figma MCP tiered data fetching protocol
- Added shared-tools (fetch_feishu_doc.py, search_prs.py, search_mrs.py, gitlab_helper.py, github_helper.py, validate_contracts.py)
- Added output workspace convention for requirement-based artifact organization
- Added phase execution guarantees and output validation for all multi-phase skills

### Marketplace

- Bumped version from 0.1.29 to 0.1.30
- Added test plugin version 0.0.1
- Removed orphaned quality plugin entry (directory does not exist)

## 0.1.29 — Remove quality plugin, refine module-discovery scope, add feishu-bot-card skill

### Spec Plugin (0.1.5)

- Changed module-discovery skill from auto-execute to on-demand (only for repos that adopt the module-index workflow)

### Sync Plugin (0.1.25)

- Added feishu-bot-card skill for sending Feishu webhook card messages
- Removed quality plugin from enabled plugins list and added cleanup for retired plugins (quality, ralph)
- Removed Ralph loop status display from statusline
- Updated ensure-codex-skills.sh to only remove symlinks (not directories) for retired skills
- Updated ensure-plugins.sh to include skill-creator and clean retired plugins
- Fixed ensure-plugins.sh to also clean retired plugins from installed_plugins.json (prevents "plugin not found" errors after plugin removal)
- Added ensure-plugins.sh Step 3: auto-clean retired plugins from current project's settings.json and settings.local.json on SessionStart
- Fixed ensure-mcp.sh to skip context7 MCP config when context7 plugin is already installed (prevents duplicate MCP server conflict)

### Marketplace

- Removed quality plugin registration from marketplace
- Bumped version from 0.1.28 to 0.1.29
- Updated spec plugin to version 0.1.5
- Updated sync plugin to version 0.1.25

## 0.1.27 — Remove context7 from auto-install plugins

### Sync Plugin (0.1.23)

- Removed `context7@claude-plugins-official` from auto-install plugin list to avoid conflict with project-level `.mcp.json` context7 config

### Marketplace

- Bumped version from 0.1.26 to 0.1.27
- Updated sync plugin to version 0.1.23

## 0.1.26 — GitLab domain migration & Codex TUI statusline

### Git Plugin (0.1.13)

- Updated self-hosted GitLab domain from `git.gametaptap.com` to `git.tapsvc.com` across code-reviewing, git-remote-operations, and gitlab-operations docs

### Sync Plugin (0.1.22)

- Added Codex official TUI `status_line` sync to `~/.codex/config.toml` via `ensure-codex-statusline.sh`
- Updated codex-statusline agent and skill docs to include Codex TUI sync
- Updated self-hosted GitLab domain from `git.gametaptap.com` to `git.tapsvc.com` in git-cli-auth command

### Marketplace

- Bumped version from 0.1.25 to 0.1.26
- Updated git plugin to version 0.1.13
- Updated sync plugin to version 0.1.22

## 0.1.25 — Codex skills sync

### Sync Plugin (0.1.21)

- Added `ensure-codex-skills.sh` to sync plugin skills to `~/.agents/skills/` for Codex discovery
- Added manifest-based tracking (`~/.cache/codex-skills-sync/managed.txt`) to safely manage symlinks without touching user-created files
- Added migration logic to clean old hardlinks and symlinks from `~/.codex/skills/` and `~/.agents/skills/`
- Added `EXCLUDE_PLUGINS` and `EXCLUDE_SKILLS` config to skip unpublished plugins (e.g., ralph)
- Added marketplace filter (`INCLUDE_MARKETPLACE`) to only sync skills from our own marketplace
- Registered `ensure-codex-skills.sh` as SessionStart hook for automatic sync on session start

### Marketplace

- Bumped version from 0.1.24 to 0.1.25
- Updated sync plugin to version 0.1.21

## 0.1.24 — Codex statusline fixes

### Sync Plugin (0.1.20)

- Fixed context usage showing 100% by using `last_token_usage.input_tokens` instead of cumulative `total_token_usage.total_tokens`
- Fixed cross-instance context usage contamination by matching sessions via filename creation timestamp
- Fixed tmux normal mode statusline not showing due to `_is_iterm2` incorrectly returning true (inherited `TERM_PROGRAM`)
- Added `_is_tmux_cc()` to properly distinguish tmux -CC from normal tmux mode
- Fixed tmux -CC mode "Unrecognized command from tmux" error by wrapping SetUserVar with tmux passthrough
- Added `_iterm2_escape()` helper for automatic tmux passthrough wrapping
- Auto-configure `allow-passthrough on` in tmux.conf (prefers `.tmux.conf.local` for framework compatibility)
- Switched iTerm2 plist operations from direct file I/O to `defaults export/import` (cfprefsd) to prevent running iTerm2 from overwriting changes
- Added `cleanup_iterm2()` function for proper Status Bar removal
- Fixed zsh hooks update detection using shasum hash comparison instead of string equality
- Added `/clean-codex-statusline` skill for complete statusline cleanup

### Marketplace

- Bumped version from 0.1.23 to 0.1.24
- Updated sync plugin to version 0.1.20

## 0.1.23 — Codex compatibility

### Sync Plugin (0.1.19)

- Added codex-statusline skill with tmux and iTerm2 support (auto-detect terminal, display project/branch/model)
- Made Codex MCP configuration optional (`--with-codex` flag) in mcp-feishu and mcp-feishu-project skills to save Codex context window space
- Migrated hooks from project-level to $HOME-level (`~/.claude/hooks/`) for Codex $HOME workspace compatibility
- Added cleanup of legacy project-level hooks in hooks-config agent
- Removed sequential-thinking MCP from configuration and templates
- Added sequential-thinking cleanup step to mcp-config agent
- Simplified `/sync:mcp` command (context7 only)
- Added plugin-status skill for runtime plugin diagnostics
- Enhanced grafana-dashboard-design skill with expanded design specifications
- Enhanced mcp-feishu and mcp-feishu-project skills with improved configuration flow
- Expanded ensure-plugins.sh with additional plugin management logic

### Git Plugin (0.1.12)

- Added environment detection to auto-select review mode: Agent Team (Claude Code) or serial dual-perspective (Codex)
- Added Mode B: serial cross-validation review for Codex — calls Claude CLI for first pass, agent does second pass, then merges findings
- Added `.agents/skills/code-reviewing/` as fallback path for review checklist and rules ($HOME Codex compatibility)
- Refactored git-flow into three standalone skills: commit, commit-push, commit-push-pr

### Marketplace

- Added `.agents/` symlink and `AGENTS.md` for Codex workspace compatibility
- Fixed hooks.md frontmatter YAML indentation error
- Bumped version from 0.1.22 to 0.1.23
- Updated git plugin to version 0.1.12
- Updated sync plugin to version 0.1.19

## 0.1.21

### Git Plugin (0.1.10)

- Added project-level custom review rules support (review-rules.md with scope-based matching)
- Redesigned code review engine: Agent Team with debate phase (2 members review independently then cross-validate)
- Added review checklist loading with project customization support (shared with CI reviewer)
- Updated plugin description to reflect new review architecture

### Sync Plugin (0.1.17)

- Added review-rules template sync to skills-sync agent (copies review-rules.md if not exists)
- Added review-rules to `/sync:basic` output and override policy docs
- Added review-rules.md template to sync plugin skills directory

### Marketplace

- Bumped version from 0.1.20 to 0.1.21
- Updated git plugin to version 0.1.10
- Updated sync plugin to version 0.1.17
- Removed ralph plugin (still in development)

## 0.1.20

### Git Plugin (0.1.9)

- Added Pipeline Watch to commit-push command (monitors existing MR pipeline after push)
- Added Pipeline Watch foreground mode with MANDATORY marker to prevent AI skipping
- Added fix-conflict skill for automated branch merge conflict resolution
- Added auto-detection and assignment of claude reviewer when creating MR

### Sync Plugin (0.1.16)

- Added review-checklist sync to skills-sync agent (skip if already exists)
- Fixed Claude Skills override policy docs in basic.md (review-checklist preserves custom version)
- Fixed missing execute permissions on 4 hook scripts
- Added Pipeline Watch to Cursor git-commit-push template
- Added MANDATORY marker to pipeline watcher in Cursor git-commit-push-pr template

### Marketplace

- Bumped version from 0.1.19 to 0.1.20
- Updated git plugin to version 0.1.9
- Updated sync plugin to version 0.1.16

## 0.1.19

### Sync Plugin (0.1.15)

- Added `/sync:lsp` command (detect project language + install LSP binary + enable plugins, with --check and --install modes)
- Added LSP binary immediate installation to `/sync:basic` Phase 2.2 (no longer deferred to next session)
- Added LSP documentation to README (commands table, config file locations, new member scenario)
- Added code review step with `--skip-code-review` to Cursor template commands (git-commit-push, git-commit-push-pr)
- Fixed MR template agent overwriting existing project templates (merged check+copy into atomic bash command)
- Updated hooks-config agent to sync 9 scripts (added ensure-lsp-tool.sh, ensure-lsp.sh)
- Updated hooks.json to include LSP tool and LSP binary hooks in SessionStart chain
- Updated ensure-plugins.sh to include ralph plugin
- Updated statusline.sh and ensure-golang.sh improvements

### Git Plugin (0.1.8)

- Added automatic code review step (before pusu) to commit-push and commit-push-pr commands with Agent Team + Codex dual-engine
- Added `--skip-code-review` parameter to skip code review
- Added `code-reviewing` skill (MR review + local review, 5-dimension checklist)
- Added `git-remote-operations` skill (GitHub/GitLab platform auto-detection, PR/MR/Issue/Pipeline management)
- Added GitHub PR support to commit-push-pr (gh CLI alongside glab)
- Added Pipeline/CI monitoring after MR/PR creation (auto-poll + failure analysis + auto-fix for lint/test)
- Changed commit-push-pr to support both GitLab and GitHub platforms
- Updated git-flow snippets (branch creation, commit execution)

### Quality Plugin (0.0.4)

- Moved `code-reviewing` skill from quality plugin to git plugin (centralized review flow)
- Removed SKILL.md, confidence-scoring.md, review-dimensions.md from quality/skills/code-reviewing/

### Marketplace

- Bumped version from 0.1.18 to 0.1.19
- Updated sync plugin to version 0.1.15
- Updated git plugin to version 0.1.8
- Updated quality plugin to version 0.0.4

## 0.1.18

### Git Plugin (0.1.7)

- Fixed missing `allowed-tools` entries for `printenv`, `echo`, `grep` in commit/commit-push/commit-push-pr commands
- Fixed missing `head`, `python3`, `cat` entries in commit-push-pr command
- Changed `GIT_ALLOW_NO_TICKET` context from `echo "$VAR"` to `printenv` for proper permission handling

### Sync Plugin (0.1.14)

- Fixed missing `allowed-tools` entries across 10 command files (git-cli-auth, mcp, hooks, cursor, statusline, basic, mcp-grafana, mcp-feishu-project, and cursor-templates)
- Added missing `printenv`, `head`, `pwd`, `cp`, `ls`, `sort`, `tail`, `echo`, `wc`, `claude`, `bash`, `mv`, `tr`, `grep`, `cat` entries where needed
- Changed `GIT_ALLOW_NO_TICKET` context in cursor-templates from `echo "$VAR"` to `printenv`

### Quality Plugin (0.0.3)

- Fixed missing `allowed-tools` entries for `mkdir`, `echo`, `date` in review command

### Spec Plugin (0.1.4)

- Fixed missing `allowed-tools` entry for `pwd` in spec command

### Marketplace

- Bumped version from 0.1.17 to 0.1.18
- Updated git plugin to version 0.1.7
- Updated sync plugin to version 0.1.14
- Updated quality plugin to version 0.0.3
- Updated spec plugin to version 0.1.4

## 0.1.17

### Git Plugin (0.1.6)

- Added `GIT_ALLOW_NO_TICKET` environment variable support for per-repo no-ticket configuration
- Added env var context line to all three commands (commit, commit-push, commit-push-pr)
- Changed no-ticket behavior: AI is now strictly prohibited from auto-inferring or filling `#no-ticket`
- Changed section 0 in commit format spec to enforce explicit user selection via AskUserQuestion
- Changed step 3 in task ID extraction to conditionally show no-ticket option based on env var
- Changed docs/style/chore type examples from `#no-ticket` to `#TAP-xxxxx` to avoid implying AI auto-use
- Added step 0 (config check) to SKILL.md execution flow

### Sync Plugin (0.1.13)

- Mirrored Git Plugin no-ticket configuration changes to cursor-templates
- Added `GIT_ALLOW_NO_TICKET` env var context to Cursor command templates
- Updated cursor-templates git-flow.mdc with repo-level config section and no-ticket rules
- Changed cursor-templates snippets (02-extract-task-id.md, 03-commit-format.md) to match git plugin

### Marketplace

- Bumped version from 0.1.16 to 0.1.17
- Updated git plugin to version 0.1.6
- Updated sync plugin to version 0.1.13

## 0.1.16

### Sync Plugin (0.1.12)

- Refactored `/sync:basic` command to use parallel agent architecture (Phase 0 path resolution + 6 named subagents)
- Reduced command execution from ~550 lines to ~150 lines (Phase 0: ≤2 Bash calls)
- Added 4 new helper scripts: `ensure-mcp.sh`, `ensure-plugins.sh`, `ensure-statusline.sh`, `ensure-tool-search.sh`
- Added `agents/` directory with 6 specialized subagents for parallel execution
- Updated `/sync:hooks` command with improved error handling and path resolution
- Updated `/sync:mcp-feishu` command with enhanced configuration logic
- Updated `/sync:mcp-feishu-project` command with streamlined setup process
- Updated `/sync:mcp-grafana` command with better validation and error messages
- Updated hooks.json configuration structure
- Updated mcp-feishu and mcp-feishu-project skill definitions

### Marketplace

- Bumped version from 0.1.15 to 0.1.16
- Updated sync plugin to version 0.1.12

## 0.1.15

### Sync Plugin (0.1.11)

- Added `/sync:statusline` command for configuring Claude Code custom status line (project/branch/context/model/worktree)
- Added MCP lazy-loading configuration to `/sync:basic` (ENABLE_TOOL_SEARCH=auto:1)
- Added Stage 6 to `/sync:basic`: Status Line configuration (copy script + update settings.json)
- Added TapTap Plugins auto-enable to `/sync:basic` (spec/sync/git/quality)
- Changed MCP config (context7 + sequential-thinking) target from project-level (`.mcp.json` / `.cursor/mcp.json`) to user-level (`~/.claude.json` / `~/.cursor/mcp.json`) for cross-project reuse
- Changed Spec Skills sync to `--with-spec` optional parameter in `/sync:basic` (not synced by default)
- Changed ensure-cli-tools.sh to run silently in background (non-blocking session startup, no terminal output)
- Changed hooks.json ensure-cli-tools to async background execution
- Cleaned up statusline.sh debug output
- Updated grafana-dashboard-design skill description

### Marketplace

- Bumped version from 0.1.14 to 0.1.15
- Updated sync plugin to version 0.1.11

## 0.1.14

### Sync Plugin (0.1.10)

- Added `/sync:mcp-feishu-project` command for configuring Feishu Project MCP (project.feishu.cn)
- Added `mcp-feishu-project` skill that auto-triggers when user provides Feishu Project MCP URL

### Marketplace

- Bumped version from 0.1.13 to 0.1.14
- Updated sync plugin to version 0.1.10

## 0.1.13

### Git Plugin (0.1.5)

- Added security restrictions: prohibited `glab mr approve` and `glab mr merge` (MR approval/merge must be manual)
- Added security restrictions: prohibited `git push --force` and variants
- Refined `allowed-tools` for push commands (removed wildcard `git push:*`, explicitly listed safe push variants)
- Added `glab` related allowed-tools (`glab mr create`, `glab auth status`, `which glab`)

### Sync Plugin (0.1.9)

- Added `/sync:mcp-grafana <username> <password>` command for Grafana MCP configuration
- Auto-installs Golang and mcp-grafana if not present
- Configures to both Claude Code and Cursor simultaneously
- Added `--dev` parameter for `/sync:basic` to prioritize cache path (for plugin developers)
- Added Stage 5: Sync Claude Skills (`grafana-dashboard-design`) to `.claude/skills/`
- Added `sync-mcp-grafana.md` Cursor command template
- Updated commit format to match git plugin (dual signature lines)

### Marketplace

- Bumped version from 0.1.12 to 0.1.13
- Updated git plugin to version 0.1.5
- Updated sync plugin to version 0.1.9

## 0.1.12

### Sync Plugin (0.1.8)

- Refactored Spec Skills sync: removed single index file `sync-claude-plugin.mdc`, now generates independent `.mdc` rule files
- Added `doc-auto-sync.mdc` - auto-sync module docs when AI modifies code (alwaysApply: true)
- Added `module-discovery.mdc` - must read module index before development (alwaysApply: true)
- Added `generate-module-map.mdc` - prompt for generating module index (alwaysApply: false)
- Filters out skills marked as "测试中" (testing): `implementing-from-task`, `merging-parallel-work`
- Auto-deletes old `sync-claude-plugin.mdc` file for backward compatibility
- Updated `/sync:basic` command to include Spec Skills sync stage

### Marketplace

- Bumped version from 0.1.11 to 0.1.12
- Updated sync plugin to version 0.1.8

## 0.1.10

### Sync Plugin (0.1.6)

- Refactored hooks architecture to use project-relative paths (`.claude/hooks/scripts/`) instead of plugin-root-relative paths
- Added `set-auto-update-plugins.sh` script to enable automatic marketplace plugin updates
- Added `sync-git-flow-snippets.sh` script for automated git-flow documentation synchronization
- Added pre-commit git hook (`.githooks/pre-commit`) for automatic snippet syncing when git-flow docs change
- Enhanced `ensure-cli-tools.sh` with detailed logging showing installation and configuration status
- Updated `hooks.json` to use project-relative script paths for better portability across team environments
- Removed Windows support: deleted `ensure-cli-tools.ps1` (macOS/Linux only)
- Removed `reload-plugins.sh` (replaced by `set-auto-update-plugins.sh`)

### Git Plugin (0.1.4)

- Modularized git-flow documentation into reusable snippets (6 files) for better maintainability
- Added support for Feishu task link extraction with automatic ID conversion
- Added support for Jira link extraction (`/browse/TAP-xxxxx` pattern)
- Enhanced task ID extraction with three-priority strategy: branch name → user input → user query
- Added mandatory second confirmation for commits without task ID (#no-ticket)
- Improved MR creation with Python-based template merging support
- Deleted monolithic `command-procedures.md` (replaced by modular snippets)

### Marketplace

- Bumped version from 0.1.9 to 0.1.10
- Updated git plugin to version 0.1.4
- Updated sync plugin to version 0.1.6

## 0.1.9

### Sync Plugin (0.1.5)

- `/sync:basic` now syncs the GitLab Merge Request default template
- Added SessionStart CLI tool checks for `gh`/`glab`, with scripts for macOS/Linux (`ensure-cli-tools.sh`) and Windows (`ensure-cli-tools.ps1`)
- Added `/sync:git-cli-auth` to detect gh/glab and configure GitHub/GitLab tokens

### Git Plugin (0.1.3)

- Refactored execution logic into reusable snippets (default branch detection, task ID extraction, branch creation, commit execution, etc.) to reduce duplication across command docs
- Tightened commit rules: title must include Chinese description; `Co-Authored-By` must be placed at the end of the body
- `commit-push-pr` can generate MR descriptions from templates (compatible with `.gitlab/merge_request_templates/default.md` and `Default.md`)

### Marketplace

- Bumped version from 0.1.8 to 0.1.9
- Updated git plugin to version 0.1.3
- Updated sync plugin to version 0.1.5

## 0.1.8

### Sync Plugin (0.1.4)

- Added `sync-claude-plugin.mdc` generation in `/sync:basic` command
- Syncs Claude Plugin Skills index to `.cursor/rules/sync-claude-plugin.mdc`
- Automatically extracts `name` and `description` from SKILL.md files
- Filters out skills marked as "测试中" (testing)
- Updated coverage strategy documentation (MCP/Hooks: skip if exists, Cursor: always overwrite)

### Spec Plugin (0.1.3)

- No functional changes, version bump for marketplace sync

### Marketplace

- Bumped version from 0.1.7 to 0.1.8
- Updated Sync plugin to version 0.1.4
- Updated Spec plugin to version 0.1.3

## 0.1.7

### Spec Plugin (0.1.2)

- Improved README with complete skills documentation
- Added `module-discovery` skill documentation (auto-read module index, keyword-based module location)
- Added `doc-auto-sync` skill documentation (layered doc system, auto-sync rules, check scripts)
- Updated `merging-parallel-work` skill documentation (worktree workflow, conflict resolution, merge report)
- Clarified trigger conditions and use cases for each skill

### Marketplace

- Bumped version from 0.1.6 to 0.1.7
- Updated Spec plugin to version 0.1.2

## 0.1.6

### Spec Plugin (0.1.1)

- Added `module-discovery` skill for AI to auto-read `module-map.md` at session start
- Added `generate-module-map.md` prompt for generating module index
- Updated `doc-auto-sync` prerequisite steps with project type and name config items

### Marketplace

- Bumped version from 0.1.5 to 0.1.6
- Updated Spec plugin to version 0.1.1

## 0.1.5

### Git Plugin (0.1.2)

- Removed support for TP- and TDS- task ID prefixes
- Simplified to support only TAP- prefix for task IDs
- Updated all documentation, commands, and regex patterns to reflect single prefix support
- Updated task ID extraction logic across all files

### Quality Plugin (0.0.2)

- Removed hardcoded absolute paths from developer's local environment
- Updated project standards file detection to use relative paths 
- Updated language-checks references to use plugin-relative paths
- Updated agent definitions path to use relative path 
- Fixed issue-comment template resource links to use correct relative paths
- Improved portability and generalization for public release

### Marketplace

- Bumped version from 0.1.4 to 0.1.5
- Updated git plugin to version 0.1.2
- Updated quality plugin to version 0.0.2

## 0.1.4

### Quality Plugin (0.0.1)

- Added AI-driven code review plugin with 9 parallel agents
- Added multi-language support (Go/Java/Python/Kotlin/Swift/TypeScript)
- Added four-dimensional review: bug detection, code quality, security analysis, performance analysis
- Added confidence scoring mechanism with redundancy confirmation (threshold: 80)
- Added intelligent project standards checking (CLAUDE.md/CONTRIBUTING.md auto-detection)
- Added `/review` command for automated code review workflow

### Sync Plugin (0.1.4)

- Improved `sync-from-zeus.sh` to auto-discover all plugins instead of hardcoding plugin names
- Removed warnings for non-existent plugins by using dynamic plugin directory scanning

### Marketplace

- Bumped version from 0.1.3 to 0.1.4
- Added quality plugin to marketplace registry

## 0.1.3

### Git Plugin (0.1.1)

- Added `/git:commit-push` command for commit and push workflow without creating MR
- Added `command-procedures.md` as shared logic layer for all commands and skills to reference
- Added intelligent branch prefix detection for `/git:commit-push-pr` (analyzes git diff to determine feat-, fix-, docs-, etc.)
- Added three-tier task ID extraction strategy (branch name → user input → ask user)
- Improved commit message format with bilingual support (English + Chinese sections)
- Improved README.md with architecture diagrams, command comparison table, and detailed workflow documentation
- Improved all command documentation to reference shared logic layer instead of duplicating procedures
- Changed commit signature format to use `Generated-By` and `Co-Authored-By` with proper spacing

### Sync Plugin (0.1.3)

- Added `cursor-templates/` directory with pre-formatted Cursor-compatible templates
- Added direct template copying approach (no runtime conversion needed)
- Improved `/sync:basic` to directly overwrite files without checking existence or conflicts
- Improved `/sync:cursor` to use three-tier template lookup and direct overwrite strategy
- Improved sync workflow to use single source of truth for Cursor format
- Changed conflict handling from interactive prompts to direct overwrite for team consistency
- Removed backup file creation (simplified sync process)

### Documentation

- Improved installation and usage instructions in root README.md
- Added detailed architecture documentation for Git plugin workflow
- Added best practices for template maintenance and customization

## 0.1.2

- Added Sync plugin with MCP and Cursor IDE synchronization features
- Improved Git plugin documentation

## 0.1.1

- Improved sync script with enhanced reliability
- Updated documentation

## 0.1.0

- Initial release with Git and Sync plugins
- Added Git workflow automation (commit, push, merge request creation)
- Added project configuration synchronization
