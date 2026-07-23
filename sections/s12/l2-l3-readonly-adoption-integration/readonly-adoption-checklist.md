# ReadOnly導入package 最終チェックリスト

このチェックリストはsynthetic/local-onlyの教材packageを確認するものです。すべて満たしても、本番導入、AWS接続、IAM適用、resource変更は承認されません。

- [x] D01 [導入スコープ](../../s1/l3-readonly-adoption-scope/examples/completed-adoption-scope.md): ReadOnly調査、対象外、人間判断、既存運用を維持する境界が明記されている。
- [x] D02 [MCP接続前確認](../../s2/l3-mcp-preconnection-checklist/examples/completed-mcp-preconnection-checklist.md): 提供経路にかかわらず、認証、IAM、監査、機密情報、prompt injection、費用を接続前に確認する。
- [x] D03 [AI作業分類](../../s3/l3-ai-work-classification/examples/completed-ai-work-classification.md): 許可、禁止、要reviewの判定が導入scopeと一致している。
- [x] D04 [IAM設計](../../s5/l3-readonly-iam-guardrails/examples/iam-guardrail-package/role-session-boundary.json): AI専用role、追跡可能session、人間operatorとの責任分離が定義され、policyを適用しない。
- [x] D05 [禁止操作](../../s5/l3-readonly-iam-guardrails/examples/iam-guardrail-package/iam-policy.json): Write、IAM変更、削除、復旧操作を明示的Denyで分離している。
- [x] D06 [監査観点](../../s6/l3-cloudtrail-audit/audit-checklist.md): AI実行、session、ticket、時間窓、CloudTrail event、errorを一意に相関する。
- [x] D07 [調査観点](../../s7/l3-incident-investigation/fixtures/expected-investigation.json): CloudWatch、Logs、Config、CloudTrailの根拠から事実、仮説、不明点、人間判断を分離している。
- [x] D08 [AI実行ログ](../../s8/l3-ai-execution-log-validation/ai-execution-log.schema.json): 実行、session、ticket、保持、masking、外部送信、判断材料、CloudTrail相関をschemaで検査する。
- [x] D09 [人間判断](../../s9/l3-human-decision-handoff/expected-results.json): 本番影響、費用、例外、permission変更、rollback不足で停止し、根拠と再開条件を渡す。
- [x] D10 [現場説明](../../s10/l3-stakeholder-adoption-review/generated/introduction.md): change approval、incident response、release processを置換せず、責任ownerを示す。
- [x] D11 [評価テスト](../../s11/l3-pre-deployment-test-pack/decision-table.md): 正常系、permission不足、機密data、停止、禁止操作、根拠不足をPASS・REVIEW・FAILで再現可能に判定する。
- [x] D12 [ReadOnly導入チェックリスト](readonly-adoption-checklist.md): D01〜D11を一つの導入判定へ接続し、AWS接続、IAM適用、本番変更を承認しない。

## 導入判定への接続

- ローカルvalidatorがpassした場合: 成果物の統合条件を満たしたため、change ownerとsecurity ownerがReadOnly pilotの可否をreviewできる。
- 1件でも欠落・矛盾・参照切れがある場合: 導入判断を停止し、該当成果物を修正して全件再検査する。
- AWS接続、IAM適用、本番data利用、本番変更が必要な場合: この演習の範囲外として停止し、別の承認済み手順で判断する。
