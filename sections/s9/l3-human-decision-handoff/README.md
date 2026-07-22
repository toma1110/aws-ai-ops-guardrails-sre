# S9: 人間判断の停止条件と引き継ぎをローカル検証する

## 目的

ReadOnly調査であっても、本番影響、費用、例外、権限変更、rollback準備のいずれかに不確実性や承認境界があれば、AIは処置を断定せず `NEED_HUMAN_DECISION` で停止します。この演習ではsyntheticな境界ケースを使い、停止理由、根拠、不明点、選択肢、next actorが一貫していることをローカルで検証します。

## 前提条件

- Python 3.11以降
- このディレクトリをローカルに取得済みであること
- AWS account、AWS CLI、credential、network接続は不要

## セットアップ

追加packageのinstallは不要です。このディレクトリへ移動してPythonを確認します。

```console
python --version
```

## 停止条件

次のどれか1つでも該当すれば `NEED_HUMAN_DECISION` です。

- `production_impact`: `possible` または `confirmed`
- `cost_impact`: `unknown` または `exceeds_approved_limit`
- `exception_required`: `true`
- `permission_change_required`: `true`
- `rollback`: `missing` または `unverified`

停止時の引き継ぎには、観測済みの根拠、まだ断定できない不明点、少なくとも2つの選択肢とtrade-off、判断できるnext actorと依頼内容が必要です。接続方法やツールの機能を、承認・安全性の代わりにはしません。

## 手順

1. `handoff-template.json` を開き、停止条件と引き継ぎfieldを確認します。
2. `fixtures/` の各scenarioで、`conditions`、`evidence`、`unknowns`、`options`、`next_actor` を対応付けます。
3. 全scenarioと期待結果を検証します。

   ```console
   python validate_handoffs.py --fixtures fixtures --expected expected-results.json
   ```

4. fail-closed testを実行します。

   ```console
   python -m unittest discover -s tests -v
   ```

5. fixture母集団を変更せず、既存のunit testを名前指定して、停止・安全な継続・不正入力の3経路を確認します。

   ```console
   python -m unittest tests.test_validation.HandoffValidationTests.test_production_impact_stops tests.test_validation.HandoffValidationTests.test_safe_readonly_can_continue tests.test_validation.HandoffValidationTests.test_incomplete_or_malformed_handoff_fails_closed -v
   ```

   この手順は `fixtures/` と `expected-results.json` を変更せず、既存test内の独立したin-memory copyだけを評価します。`test_production_impact_stops` は停止条件で `NEED_HUMAN_DECISION`、`test_safe_readonly_can_continue` は安全なReadOnlyで `CONTINUE_READONLY`、`test_incomplete_or_malformed_handoff_fails_closed` は引き継ぎfieldの欠落・破損で `INVALID_INPUT` になることを検証します。

## 期待結果

- validatorは7 fixtureを検査し、`PASS: 7 scenarios matched expected results` と終了コード0を返す
- 6件は `NEED_HUMAN_DECISION`、安全なReadOnly 1件だけが `CONTINUE_READONLY`
- unit testは9件すべてpass
- 停止scenarioは根拠、不明点、2つ以上の選択肢、next actorを欠かさない

## Cost / cleanup

この演習はローカルJSONを読むだけで、AWSへ接続せずresourceも作成しません。AWS費用は0で、手順中に一時fixtureを作成しないためcleanup対象はありません。この手順は削除commandを実行しません。

## Troubleshooting

- `python` が見つからない: Python 3.11以降をinstallし、PATHを確認します。
- `fixture population does not exactly match`: `fixtures/*.json` と `expected-results.json` のfilename集合を一致させます。
- `INVALID_INPUT`: 表示されたreason codeを確認し、根拠、不明点、選択肢、next actor、条件の型を見直します。
- 期待外に継続する: 5つの停止条件の値と、期待結果のreason codeを確認します。
- 実環境で試したくなった: credential、account ID、本番ログを使わず、この教材に含まれるsynthetic fixtureとunit testだけで検証します。

## 安全境界

PASSが証明するのは、この教材のlocal fixtureと決定規則が一致することだけです。実際の本番影響、費用、権限、例外承認、rollback可能性、AWS API結果、組織固有の承認者を証明しません。実環境では変更を実行せず、該当system owner、incident commander、security、financeなど組織が定めた人間へ引き継いでください。
