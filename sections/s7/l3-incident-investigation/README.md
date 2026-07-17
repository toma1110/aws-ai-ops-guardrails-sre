# 根拠付き障害調査レポートをローカルfixtureから作る

CloudWatchメトリクス・Logs、CloudTrail、AWS Config、ALB・EC2・RDS相当の合成fixtureをUTC時系列で関連付け、事実、仮説、不明点、人間判断を混ぜずに整理します。AWSへ接続せず、認証情報も使いません。

## 到達目標

- メトリクス閾値とERRORログから最初の異常時刻を抽出する
- CloudTrail変更イベントとConfig履歴を同一event/resourceで関連付ける
- ALB、EC2、RDSの同時刻状態を並べ、1つの観測だけで原因を断定しない
- 各事実・仮説を正しい `evidence_id` に結び付ける
- 変更や追加アクセスを人間判断へ引き継ぐ

## 前提とセットアップ

- Python 3.11以上（標準ライブラリだけを使用）
- このディレクトリを作業ディレクトリにする
- AWS CLI、AWS account、credentialは不要

バージョンを確認します。

```console
python --version
```

## 手順

1. `fixtures/incident-observations.json` を開き、`window_start` / `window_end` と、5種類の証跡群を確認します。すべて架空データです。
2. `MET-002`、`MET-003` の値を `metric_thresholds` と比較し、`LOG-001` の時刻と合わせて最初の異常時刻を探します。
3. `CT-001.event_id` と `CFG-001.related_event_id`、両方の `resource` を突合します。時刻が近いだけでは同じ変更の証拠にしません。
4. `ALB-001`、`EC2-001`、`RDS-001` と各サービスのメトリクスを同じUTC時刻で並べます。
   validatorは各pairのexpected namespace、metric name、service、resource、timestamp完全一致を検査します。resourceや時刻が異なる観測を同じ状態の証拠へ流用しません。
5. [レポートテンプレート](templates/investigation-report.md) の事実、仮説、不明点、人間判断を別々に埋めます。事実と仮説には必ず対応する `evidence_id` を付けます。
6. validatorを実行し、生成結果をexact expected JSONと比較します。

```console
python scripts/investigate_incident.py
```

7. 必要なら検査済みJSONを任意の一時pathへ出力します（この成果物には生成済みreportを含めません）。

```console
python scripts/investigate_incident.py --write-report investigation-report.json
```

8. 正ケースとfail-closed負ケースを実行します。

```console
python -m unittest discover -s tests -v
```

## 期待結果

標準出力は [expected-results/investigation.txt](expected-results/investigation.txt) と一致します。最初の異常は `2026-07-17T00:03:30Z`、分類数は事実7、仮説2、不明点2、人間判断2です。exactな構造は `fixtures/expected-investigation.json` で比較されます。

標準出力はredirect時もUTF-8・LFへ固定されます。test suiteはsubprocessのstdout bytesを期待ファイルと直接比較し、WindowsのCRLF混入も拒否します。

成功は合成fixtureの相関と分類が再現できたことだけを示します。属性変更が障害原因であること、RDS障害があったこと、実環境のログが完全であることは示しません。

## 費用、cleanup、安全境界

- 必須演習はローカル完結でAWS費用は0です。
- AWS接続、API呼び出し、resource作成・変更・削除、IAM変更を行いません。
- cleanupは不要です。手順7で自分が作成した `investigation-report.json` が不要なら、そのファイルだけを削除してください。
- 実環境へ応用する場合も、追加ログへのアクセスとrollbackは人間の承認・既存手順に従います。credential、氏名、customer dataをfixtureやreportへ貼り付けないでください。

## トラブルシューティング

- `INVALID - generated report does not exactly match expected investigation`: fixtureと期待値のどちらかが変わっています。差分を確認し、期待値を都合よく緩めずに証跡の意味を再確認します。
- `Config change must correlate ...`: CloudTrail event IDとresourceの両方が一致していません。
- `must reference the same resource` / `must have the same timestamp`: service別metric/state pairへ別resourceや別時刻の証跡が混ざっています。
- `outside the incident window`: UTC時刻または調査時間帯を確認します。
- Windowsで文字化けする場合はUTF-8対応terminalを使い、`PYTHONUTF8=1` を設定して再実行します。
