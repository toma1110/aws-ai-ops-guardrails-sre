# Security review checklist

## 共通確認

- [ ] 既存の変更承認、障害対応、release processを置き換えない
- [ ] AI出力を確定事実または承認として扱わない
- [ ] decision ownerとsecurity ownerを特定する

## 懸念別確認

- [ ] **CHANGE**: AIの役割が調査補助に限定され、変更操作が既存承認を迂回しない（owner: change approver）
- [ ] **LOG**: ログの目的、最小化、masking、保持、閲覧権限、外部送信境界が明記されている（owner: security reviewer）
- [ ] **ACCOUNTABILITY**: 誤回答時の判断者、検証方法、訂正、エスカレーションの責任分界が明記されている（owner: incident commander）
- [ ] **API_CONNECTION**: 接続前reviewがあり、接続方法と権限・監査・承認が別の境界として扱われている（owner: security reviewer）

## review evidence

- [ ] **CHANGE**: 変更権限を持たない設計と、既存承認フローを維持する運用手順
- [ ] **LOG**: 記録項目、masking規則、保持期間、閲覧権限、外部送信先のreview結果
- [ ] **ACCOUNTABILITY**: 根拠、不明点、判断者、エスカレーション先を含む報告形式
- [ ] **API_CONNECTION**: 接続前checklistと、許可API、拒否操作、監査方法、停止条件のreview結果
