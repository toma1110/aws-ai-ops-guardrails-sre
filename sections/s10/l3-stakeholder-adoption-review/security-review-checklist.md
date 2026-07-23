# Security review checklist

`判定`は`pass`、`review`、`fail`のいずれかにします。根拠がない項目を`pass`にしません。

| 観点 | 確認事項 | 判定 | 根拠 | Owner |
| --- | --- | --- | --- | --- |
| scope | ReadOnly調査補助の対象と禁止操作が明確か |  |  |  |
| identity / permission | 専用identity/session、最小権限、permission変更の承認境界が明確か |  |  |  |
| data / log | 送信範囲、マスキング、保持、閲覧権限が明確か |  |  |  |
| prompt injection | 信頼しない入力とtool実行を分離し、疑わしい指示で停止するか |  |  |  |
| auditability | AI実行とAPI監査を相関し、根拠を追跡できるか |  |  |  |
| human approval | 誤回答の責任境界と、変更・release・復旧の人間承認が明確か |  |  |  |
| incident / exit | 停止、連絡、無効化、既存運用へ戻る方法が明確か |  |  |  |

## 総合判定

- 判定:
- 未解決事項:
- 次のownerとaction:
- 再review条件:
