# CloudTrail相関監査チェックリスト

- [ ] 対象の`execution_id`がAI実行ログに一意に存在する
- [ ] 実行ログに`session`、`ticket_id`、UTCの開始・終了時刻がある
- [ ] CloudTrail eventの`userIdentity.type`が`AssumedRole`である
- [ ] `principalId`末尾とassumed-role ARN末尾の両方が対象sessionに一致する
- [ ] `eventTime`が対象実行の時間窓内にある
- [ ] 各eventからidentity、event、source、parameters、errorを抽出した
- [ ] APIエラーなしは`null`、エラーありはcodeとmessageを保持した
- [ ] 抽出event IDの順序と内容を承認済み期待結果と比較した
- [ ] sessionが同じでも時間窓が重なる実行があれば曖昧として拒否した
- [ ] 無関係な人間sessionや別AI実行を根拠へ混ぜていない
- [ ] fixtureがsynthetic/local-onlyで、credential、実account ID、PII、secretを含まない
- [ ] AWSへ接続・照会・変更していない

このチェックリストはローカルfixtureの相関完全性だけを確認します。実環境のCloudTrail設定、記録範囲、ログ完全性、改ざん耐性、保持期間は証明しません。
