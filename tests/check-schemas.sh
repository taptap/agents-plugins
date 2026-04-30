#!/usr/bin/env bash
# 校验 plugins/test/contracts/ 下的 JSON Schema 文件：
#   1. schema 自身可被 jsonschema 加载
#   2. 用样本数据验证：合法数据通过、典型非法数据被拒
#
# 通过 tests/validate.sh 和 .pre-commit-config.yaml 调用。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTRACTS_DIR="${REPO_ROOT}/plugins/test/contracts"

for f in testcase ca-summary defect-list rr-summary smoke-test-report; do
  if [[ ! -f "${CONTRACTS_DIR}/${f}.schema.json" ]]; then
    echo "❌ ${f}.schema.json not found at ${CONTRACTS_DIR}" >&2
    exit 1
  fi
done

python3 - "$CONTRACTS_DIR" <<'PYEOF'
import json
import sys
from pathlib import Path

import jsonschema

contracts_dir = Path(sys.argv[1])

def load(name: str) -> dict:
    return json.load(open(contracts_dir / f'{name}.schema.json'))

def assert_valid(label: str, schema: dict, data) -> None:
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        sys.exit(f'合法数据被拒绝 [{label}]: {e.message}')

def assert_invalid(label: str, schema: dict, data) -> None:
    try:
        jsonschema.validate(data, schema)
        sys.exit(f'非法数据未被拒绝 [{label}]')
    except jsonschema.ValidationError:
        pass

# ============================================================
# testcase.schema.json
# ============================================================
testcase = load('testcase')
assert_valid('testcase ok', testcase, [{
    'title': '登录成功',
    'priority': 'P0',
    'preconditions': ['账号已注册'],
    'steps': [{'action': '输入凭证', 'expected': '校验通过'}],
}])
for label, data in [
    ('testcase priority enum',
     [{'title': 't', 'priority': 'P9', 'preconditions': [], 'steps': [{'action': 'a'}]}]),
    ('testcase title 非空',
     [{'title': '', 'priority': 'P0', 'preconditions': [], 'steps': [{'action': 'a'}]}]),
    ('testcase 禁止额外字段',
     [{'title': 't', 'priority': 'P0', 'preconditions': [], 'steps': [{'action': 'a'}], 'name': 'x'}]),
    ('testcase steps 非空',
     [{'title': 't', 'priority': 'P0', 'preconditions': [], 'steps': []}]),
]:
    assert_invalid(label, testcase, data)

# ============================================================
# ca-summary.schema.json
# ============================================================
ca = load('ca-summary')
assert_valid('ca-summary ok', ca, {
    'changed_modules': ['user-service/auth.go'],
    'risk_count': 3,
    'new_features': [{'title': '新增登录校验', 'module': 'auth'}],
    'risk_breakdown': {'high': 1, 'medium': 2, 'low': 0},
})
for label, data in [
    ('ca-summary 缺 required',
     {'changed_modules': ['x']}),
    ('ca-summary 拼错 modules',
     {'changed_modules': [], 'risk_count': 0, 'modules': ['x']}),
    ('ca-summary 拼错 risks_count',
     {'changed_modules': [], 'risk_count': 0, 'risks_count': 1}),
    ('ca-summary 拼错 features',
     {'changed_modules': [], 'risk_count': 0, 'features': []}),
    ('ca-summary risk_count 负数',
     {'changed_modules': [], 'risk_count': -1}),
]:
    assert_invalid(label, ca, data)

# ============================================================
# defect-list.schema.json
# ============================================================
defects = load('defect-list')
assert_valid('defect-list ok', defects, {
    'defects': [{
        'id': 'DEFECT-1',
        'name': '登录失败时未提示',
        'priority': 'P0',
        'category': 'implementation_missing',
        'description': '点击登录无反馈',
        'expected_result': '弹出错误提示',
        'actual_result': '页面静默',
    }],
})
assert_valid('defect-list 空列表', defects, {'defects': []})
for label, data in [
    ('defect-list 缺 priority',
     {'defects': [{'name': 'x'}]}),
    ('defect-list 缺 name',
     {'defects': [{'priority': 'P0'}]}),
    ('defect-list priority enum',
     {'defects': [{'name': 'x', 'priority': 'P3'}]}),
    ('defect-list 拼错 title',
     {'defects': [{'name': 'x', 'priority': 'P0', 'title': 'y'}]}),
    ('defect-list 拼错 actual',
     {'defects': [{'name': 'x', 'priority': 'P0', 'actual': 'y'}]}),
    ('defect-list 拼错 expected',
     {'defects': [{'name': 'x', 'priority': 'P0', 'expected': 'y'}]}),
    ('defect-list 拼错 desc',
     {'defects': [{'name': 'x', 'priority': 'P0', 'desc': 'y'}]}),
]:
    assert_invalid(label, defects, data)

# ============================================================
# rr-summary.schema.json
# ============================================================
rr = load('rr-summary')
assert_valid('rr-summary ok', rr, {
    'verdict': 'ready_with_conditions',
    'issue_count': 2,
    'blocking_issues': [{'title': 'PRD 缺异常分支', 'category': '完整性'}],
})
for label, data in [
    ('rr-summary 缺 required',
     {'verdict': 'ready'}),
    ('rr-summary verdict enum',
     {'verdict': 'go', 'issue_count': 0}),
    ('rr-summary 拼错 result',
     {'verdict': 'ready', 'issue_count': 0, 'result': 'ok'}),
    ('rr-summary 拼错 conclusion',
     {'verdict': 'ready', 'issue_count': 0, 'conclusion': 'ok'}),
    ('rr-summary 拼错 issues_count',
     {'verdict': 'ready', 'issue_count': 0, 'issues_count': 1}),
    ('rr-summary 拼错 blockers',
     {'verdict': 'ready', 'issue_count': 0, 'blockers': []}),
]:
    assert_invalid(label, rr, data)

# ============================================================
# smoke-test-report.schema.json
# ============================================================
smoke = load('smoke-test-report')
assert_valid('smoke ok', smoke, {
    'verdict': 'pass',
    'fail_reason': None,
    'verification_summary': {
        'total_points': 10, 'passed': 9, 'failed': 0, 'inconclusive': 1,
        'verification_rate': '90%',
    },
    'defect_summary': {
        'total': 1,
        'by_priority': {'P0': 0, 'P1': 1, 'P2': 0},
        'by_category': {'implementation_missing': 1},
    },
})
for label, data in [
    ('smoke 缺 required verdict',
     {'verification_summary': {}, 'defect_summary': {'total': 0}}),
    ('smoke verdict enum',
     {'verdict': 'unknown', 'verification_summary': {}, 'defect_summary': {'total': 0}}),
    ('smoke 拼错 result',
     {'verdict': 'pass', 'result': 'ok', 'verification_summary': {}, 'defect_summary': {'total': 0}}),
    ('smoke 拼错 verdicts',
     {'verdict': 'pass', 'verdicts': [], 'verification_summary': {}, 'defect_summary': {'total': 0}}),
    ('smoke 拼错 defects_summary',
     {'verdict': 'pass', 'verification_summary': {}, 'defects_summary': {'total': 0}, 'defect_summary': {'total': 0}}),
    ('smoke defect_summary 缺 total',
     {'verdict': 'pass', 'verification_summary': {}, 'defect_summary': {}}),
    ('smoke defect_summary 拼错 priority_distribution',
     {'verdict': 'pass', 'verification_summary': {}, 'defect_summary': {'total': 0, 'priority_distribution': {}}}),
]:
    assert_invalid(label, smoke, data)

print('ok')
PYEOF
