# S12: ReadOnly導入packageを最終検証する

## 目的

架空のローカル環境を対象に、Courseで作成した12成果物を一つのReadOnly導入packageとして接続します。成果物の欠落、参照切れ、依存関係の矛盾、安全境界の後退を機械検査し、人間が導入判定を始められる状態か確認します。

## 前提条件

- Python 3.11以降
- MarkdownとJSONを読めること
- repositoryをローカルに取得済みであること
- AWS account、AWS CLI、credential、network接続は不要

## 安全境界

この演習はsynthetic/local-onlyです。AWSへ接続せず、account IDやcredentialを入力せず、IAM policyを適用しません。resourceの作成・変更・削除、本番変更、自動復旧、外部送信は行いません。検査結果の`PASS`は「ローカル教材の統合条件を満たした」という意味であり、本番導入やAWS変更を承認しません。

## セットアップ

追加packageは不要です。repository rootでPythonを確認します。

```console
python --version
```

主なファイルは次のとおりです。

- `deliverable-index.json`: 12成果物の正規順序、実体path、依存関係
- `readonly-adoption-checklist.md`: 人間が読む最終チェックリスト
- `integration-package.schema.json`: 統合packageのJSON schema
- `fixtures/sample-integration-package.json`: syntheticな完成例
- `fixtures/invalid-write-enabled.json`: Write境界の後退を表す失敗例
- `validate_integration.py`: index、実体、checklist、links、schema、sampleを検査するvalidator
- `tests/`: 安全境界とcross-referenceの後退を検出するsample tests

## 手順

1. [ReadOnly導入チェックリスト](readonly-adoption-checklist.md)を開き、架空環境の制約と12成果物の完成条件を確認します。
2. 成果物1〜3を読み、導入scope、MCP接続前確認、AI作業分類が同じReadOnly境界を使っていることを確認します。
   - [導入スコープ](../../s1/l3-readonly-adoption-scope/examples/completed-adoption-scope.md)
   - [MCP接続前チェックリスト](../../s2/l3-mcp-preconnection-checklist/examples/completed-mcp-preconnection-checklist.md)
   - [AI作業分類表](../../s3/l3-ai-work-classification/examples/completed-ai-work-classification.md)
3. 成果物4〜5を読み、AI専用sessionと最小権限IAMに加え、禁止操作が明示的Denyとして分離されていることを確認します。policy例は読むだけで、AWSへ適用しません。
   - [role/session境界](../../s5/l3-readonly-iam-guardrails/examples/iam-guardrail-package/role-session-boundary.json)
   - [IAM policy例](../../s5/l3-readonly-iam-guardrails/examples/iam-guardrail-package/iam-policy.json)
4. 成果物6〜8を読み、CloudTrail監査、CloudWatch・Config調査、AI実行ログが相互に追跡でき、事実・仮説・不明点・人間判断が混ざっていないことを確認します。
   - [CloudTrail監査チェックリスト](../../s6/l3-cloudtrail-audit/audit-checklist.md)
   - [根拠付き調査結果](../../s7/l3-incident-investigation/fixtures/expected-investigation.json)
   - [AI実行ログschema](../../s8/l3-ai-execution-log-validation/ai-execution-log.schema.json)
5. 成果物9〜11を読み、停止条件、現場説明、導入前評価が本番変更ではなく人間の導入判定へ接続していることを確認します。
   - [人間判断の期待結果](../../s9/l3-human-decision-handoff/expected-results.json)
   - [現場向け導入説明](../../s10/l3-stakeholder-adoption-review/generated/introduction.md)
   - [導入前評価判定表](../../s11/l3-pre-deployment-test-pack/decision-table.md)
6. `fixtures/sample-integration-package.json`を開き、各`depends_on`が`deliverable-index.json`の依存関係と一致し、12件すべてが`pass`であることを確認します。
7. repository rootからvalidatorを実行します。

   ```console
   python sections/s12/l2-l3-readonly-adoption-integration/validate_integration.py
   ```

8. S12のsample testsを実行します。

   ```console
   python -m unittest discover -s sections/s12/l2-l3-readonly-adoption-integration/tests -v
   ```

9. 自組織で試す場合はfixtureのcopyを作り、実account ID、credential、実ログ、個人情報を入れず、承認済みsynthetic dataだけを使用します。判断結果を本番変更の承認として使わず、change ownerとsecurity ownerのreviewへ渡します。

## 期待結果

validatorは次を表示して終了コード0を返します。

```text
sample-integration-package.json: PASS
invalid-write-enabled.json: EXPECTED_FAIL
PASS: 12 deliverables, checklist, links, schema, and sample tests are consistent
```

unit testは、正規sampleの成功に加え、AWS接続、IAM適用、Write有効化、成果物欠落、依存関係改変、schema後退、checklist欠落、リンク切れを拒否します。

## Cost / cleanup

ローカルのMarkdown、JSON、Pythonを読むだけなのでAWS費用は0です。AWS resource、IAM、credential、一時cloud resourceを作成しないためAWS cleanupは不要です。Pythonが作る`__pycache__`などの一時fileは検査対象成果物ではありません。

## Troubleshooting

- `deliverable_index_not_canonical`: 成果物名、順序、path、依存関係を独自に緩和せず、教材の`deliverable-index.json`と照合します。
- `artifact_missing`: 表示されたS1〜S12の相対pathが存在するか確認します。別成果物を代用して合格にしません。
- `markdown_link_missing`: READMEまたはchecklistの相対linkを修正します。local absolute pathへ置き換えません。
- `schema_contract_invalid`: safety境界の`const`、12件固定、必須fieldを緩和していないか確認します。
- `aws_connection_must_be_false` / `iam_policy_application_must_be_false`: fixtureをローカル専用へ戻します。credentialやAWS接続を追加しません。
- `dependency_graph_invalid`: `deliverable-index.json`の依存関係へ戻し、後工程の成果物で前工程を代用しません。
- `production_change_must_not_be_authorized`: 本番変更の承認を外し、次の行動を人間の導入reviewへ戻します。
