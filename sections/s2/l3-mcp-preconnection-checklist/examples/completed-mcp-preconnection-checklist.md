# MCP接続前リスクチェックリスト（完成例）

## 評価対象

- 提供経路: managed-aws-mcp
- 利用目的: 架空の検証環境でReadOnly調査の接続前要件をレビューする
- 対象環境: 架空の非本番環境。実在するaccountやresourceは含まない
- 公式情報の再確認日: 2026-07-13
- 公式情報URL: https://docs.aws.amazon.com/agent-toolkit/latest/userguide/mcp-server.html

## リスク評価

| 分類 | 判定 | 根拠 | owner | 再確認日 | 停止条件 |
| --- | --- | --- | --- | --- | --- |
| CONNECTION | REVIEW | CONNECTION-01: network経路と利用環境のレビュー記録がない | Platform owner | 2026-07-13 | 許可環境とnetwork経路を承認できるまで接続しない |
| PERMISSIONS | BLOCK | PERMISSIONS-01: 許可API actionとsession分離が未検証 | IAM owner | 2026-07-13 | 最小権限とsession分離の検証が終わるまで接続しない |
| AUDIT | REVIEW | AUDIT-01: 追跡項目はあるが保持期間が未承認 | Audit owner | 2026-07-13 | 保持期間と閲覧権限を承認できるまで接続しない |
| SENSITIVE_DATA | BLOCK | SENSITIVE_DATA-01: maskingとログ保持範囲が未決定 | Data owner | 2026-07-13 | maskingと保存境界を承認できるまで接続しない |
| PROMPT_INJECTION | PASS | PROMPT_INJECTION-01: 信頼できない入力に対する停止条件が定義済み | Security owner | 2026-07-13 | 外部入力が命令として扱われた場合は直ちに停止する |
| COST | REVIEW | COST-01: 予算上限と利用停止基準が未承認 | FinOps owner | 2026-07-13 | 予算上限と通知先を承認できるまで接続しない |

## 監査で追跡する項目

- actor/identity: AI専用identityを一意に識別する
- timestamp: UTCのイベント時刻を記録する
- API operation: 呼び出したAWS API actionと対象を記録する
- session/correlation ID: AI実行とAPI監査を結び付けるIDを記録する

## 総合判定

- 接続前判定: DO_NOT_CONNECT
- 判定理由: PERMISSIONSとSENSITIVE_DATAがBLOCKであり、接続前の必須制御が未完了
- 承認者: 差戻し
