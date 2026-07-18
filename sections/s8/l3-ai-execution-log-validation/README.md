# S8: AI実行ログJSONをローカル検証する

## 目的

CloudTrailのイベントは「どのidentityが、どのAWS APIを、いつ呼んだか」を監査する記録です。一方、AI実行ログは「AIへ何を入力し、何を出力し、どの判断材料を使い、どの実行・session・ticketに属するか」を説明する記録です。片方で他方を代用せず、必要なら `cloudtrail_correlation.event_ids` で相関します。

この演習ではAI実行ログの相関情報、保持期限、マスキング、外部送信境界をJSON Schemaとローカルpolicy checkで検証します。`masked_fields` は `input` または `output` から始まるdot pathだけを許可し、全pathを実データへ解決します。存在しないpath、object/array、未対応pathはfail closedです。

masking形式は曖昧な平文と区別できる次の3種類です。

- `redact`: exact `[REDACTED]`
- `tokenize`: `token-` と小文字英数字・hyphenから成るtoken
- `hash`: `sha256:` に64桁の小文字hexを続けた値

## 前提条件

- Python 3.11以降
- このディレクトリをローカルに取得済みであること
- AWS account、AWS CLI、credential、network接続は不要

## セットアップ

追加packageのinstallは不要です。このディレクトリへ移動し、次を確認します。

```console
python --version
```

## 手順

1. `ai-execution-log.schema.json` を開き、必須の `execution_id`、`session_id`、`ticket_id` と、保持・マスキング・外部送信の構造を確認します。
2. `fixtures/valid-local.json` を開き、機密値が `[REDACTED]` で、外部送信が `none` であることを確認します。
3. 全fixtureと期待結果を検証します。

   ```console
   python validate_logs.py --fixtures fixtures --expected expected-results.json
   ```

4. fail-closedの自動testを実行します。

   ```console
   python -m unittest discover -s tests -v
   ```

5. invalid fixtureを1つずつ確認し、相関field欠落、保持超過、未マスキング、masking宣言pathの不存在、宣言pathに残る平文、未承認外部送信、平文機密マーカーが拒否される理由を `expected-results.json` と対応付けます。

## 期待結果

- validatorは9 fixtureを検査し、`PASS: 9 fixtures matched expected results` と終了コード0を返す
- `valid-local.json` と `valid-approved-external.json` の2件だけがvalid
- 7件のinvalid fixtureは期待したreason codeでfail closed
- unit testは11件すべてpass

`valid-approved-external.json` は承認済み送信境界の構造例であり、実際の外部送信を行いません。この演習はファイルを読むだけです。

## Cost / cleanup

AWSへ接続せずresourceも作成しないため、AWS費用は0です。cleanup対象はありません。必要ならローカルに作成したcopyだけを利用者自身の判断で削除してください。この手順は削除commandを実行しません。

## Troubleshooting

- `python` が見つからない: Python 3.11以降をinstallし、PATHを確認します。
- fixture population error: `fixtures/*.json` と `expected-results.json` のfilename集合を一致させます。
- JSON parse error: trailing comma、引用符、UTF-8保存を確認します。
- 期待外のinvalid: stdoutの `reason_codes` を確認し、schema構造と保持・マスキング・外部送信境界を見直します。
- 実データを試したくなった: credential、個人情報、account ID、本番ログを使わず、synthetic copyだけで検証します。

## 安全境界

この教材は宣言済みの `input` / `output` sensitive pathと、教材に列挙した限定markerだけを検査します。任意のPIIやsecretを普遍的に分類するものではありません。またAWS API監査の完全性、CloudTrail delivery、ログ改ざん防止、組織の正式な保持期間、実在する外部serviceの承認を証明しません。production適用はsecurity・legal・privacy・運用ownerによる別reviewが必要です。
