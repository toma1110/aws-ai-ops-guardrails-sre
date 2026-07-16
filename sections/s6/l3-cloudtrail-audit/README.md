# Section 6: CloudTrail sample eventをAI実行へ相関する

この演習ではsyntheticなローカルfixtureだけを使い、CloudTrail eventのidentity、event、source、parameters、errorを抽出し、AI実行ID・session・ticket IDとAWS API eventを相関して期待結果と比較します。AWSへは接続しません。

## 到達目標

- CloudTrail eventから5つの監査項目を欠落なく読む
- AI実行ログの`execution_id`と`ticket_id`を、共有sessionとUTC時間窓でCloudTrail eventへ結合する
- 成功eventとAPI error eventを区別し、無関係eventを除外する
- 相関結果を承認済み期待値と完全比較し、曖昧・欠落・ずれをfail closedにする

## 前提条件とセットアップ

- Python 3.10以上（標準ライブラリのみ）
- JSONとMarkdownを読めるeditor
- このREADMEがあるdirectoryで`python --version`を実行できること

AWS account、credential、AWS CLI、network接続、追加packageは不要です。repositoryを取得済みなら追加セットアップもありません。

> **費用・安全:** 全入力は架空です。`000000000000`、`198.51.100.0/24`、`i-synthetic...`は教材用表現であり、実account・利用者・resourceを示しません。AWS API、resource作成、IAM変更はなく、AWS費用は0です。実account ID、ARN、IP、氏名、ticket、secret、credentialをfixtureへ貼らないでください。

## 構成

- `fixtures/ai-executions.json`: 実行ID、session、ticket ID、UTC時間窓
- `fixtures/cloudtrail-events.json`: 対象2件、無関係な人間session 1件、別AI実行1件
- `fixtures/expected-audit.json`: 対象実行の承認済み期待値
- `scripts/audit_cloudtrail.py`: 相関query、5項目抽出、期待値比較
- `audit-checklist.md`: 手動監査の確認表
- `tests/fixtures/`: 曖昧相関、監査項目欠落、期待値ずれのnegative cases

## 相関ルール

CloudTrailにはこの教材のAI実行IDやticket IDを直接記録したことにしません。まずAI実行ログで`execution_id → ticket_id + session + time window`を一意に選び、次にCloudTrailの`principalId`末尾とassumed-role ARN末尾が同じsessionで、`eventTime`が時間窓内のeventだけを結合します。同一sessionの実行時間窓が重なる場合は曖昧なので拒否します。

## 演習手順

1. `fixtures/ai-executions.json`を開き、`AI-EXEC-006`のsession、ticket、開始・終了を確認します。
2. `fixtures/cloudtrail-events.json`で4件の`userIdentity`、`eventName`、`eventSource`、`requestParameters`、error有無を読みます。
3. 対象sessionが一致し、00:00–00:05Z内にあるevent IDを手で選びます。人間sessionと01:01Zの別実行は除外します。
4. `audit-checklist.md`を使い、sessionをprincipal IDとARNの両方で確認します。
5. query/validatorを実行します。

   ```console
   python scripts/audit_cloudtrail.py --execution-id AI-EXEC-006
   ```

6. 出力を`expected-results/audit.txt`と比較します。validator自身も`fixtures/expected-audit.json`と全event ID・5監査項目を完全比較します。
7. negative casesを確認します。以下はいずれも終了code 1と`INVALID`でなければなりません。

   ```console
   python scripts/audit_cloudtrail.py --executions tests/fixtures/invalid-ambiguous-executions.json
   python scripts/audit_cloudtrail.py --events tests/fixtures/invalid-missing-parameters.json
   python scripts/audit_cloudtrail.py --expected tests/fixtures/invalid-expected-audit.json
   ```

8. 全testを実行します。

   ```console
   python -m unittest discover -s tests -v
   ```

## 期待結果

`AI-EXEC-006`は`INC2042`と`ai-analyst-INC2042-run06`へ結合され、2件だけを時刻順に抽出します。1件目はCloudWatch `GetMetricData`でerrorなし、2件目はLogs `FilterLogEvents`でsyntheticな`AccessDenied`です。出力末尾は`expected_comparison: PASS`と`aws_connection: false`です。

positive caseが成功し、曖昧な重複session、`requestParameters`欠落、期待event IDずれ、identity不整合、error片側欠落、local safety宣言違反が拒否されることがfail-closedの期待結果です。

## 証明すること・しないこと

この演習はローカルfixtureでのschema検査、session/time相関、5項目抽出、期待値比較だけを証明します。実CloudTrailの有効化、記録対象、完全性、Lake query、ログ配送、保持、改ざん耐性、AWS上の権限やAPI結果は証明しません。実環境では承認済みReadOnly手順、対象account/region、ログsource、保持・整合性設定を人間のsecurity reviewerが別途確認してください。

## クリーンアップ

AWS側のcleanupは不要です。resourceやcredentialを作成・変更していません。scriptは入力を読み取るだけで自動削除・書換えを行いません。自分が作ったローカルcopyだけを、所有pathを確認して通常のファイル操作で整理してください。

## トラブルシューティング

- `python`がない: Python 3.10以上をPATHへ追加し、環境に応じて`py -3`または`python3`を試します。
- `cannot read`: README directoryから実行し、JSONのcomma、quote、braceとUTF-8保存を確認します。
- `no CloudTrail events matched`: execution ID、sessionの大文字小文字、UTC時間窓を確認します。
- `inconsistent session identity`: `principalId`末尾とassumed-role ARN末尾の両方を同じsessionにします。
- `ambiguous correlation`: sessionを実行ごとに一意にするか、重ならない正しい時間窓を記録します。推測で選びません。
- `expected ... do not exactly match`: 抽出結果を監査し、期待値変更をreviewなしで正当化しないでください。

教材version 1.0.0 / fixture schema 1 / Python 3.10+標準ライブラリのみ。
