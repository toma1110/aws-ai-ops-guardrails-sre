# Section 2: MCP接続前リスクチェックリストを作る

この演習では、AWS MCPの提供経路を選ぶ前に、接続そのものと運用上の安全性を分けて評価します。ローカルのシナリオfixtureを読み、6つの必須リスク分類を1枚のMarkdownチェックリストにまとめます。

## 到達目標

- Marketplace AWS API MCP Serverとmanaged AWS MCP Serverの提供経路・責任境界を混同せずに比較する
- 接続、権限、監査、機密情報、prompt injection、費用を接続前に評価する
- 根拠がない項目を推測で`PASS`にせず、`REVIEW`または`BLOCK`で止める
- 各判定に根拠、担当者、再確認日、停止条件を残す

## 前提条件

- Python 3.10以上
- MarkdownとJSONを編集できるテキストエディタ
- ターミナル（PowerShell、コマンドプロンプト、または一般的なUnix shell）

AWSアカウント、AWS認証情報、MCP Server、追加のPythonパッケージは不要です。

> **費用と安全性:** 必須演習はローカルファイルを読み取るだけで、AWSへ接続しません。AWSリソースを作成・変更・削除しないため、AWS利用料金は発生せず、AWS側のcleanupも不要です。アカウントID、アクセスキー、token、実ログ、顧客情報を教材へ記入しないでください。

## 比較するときの前提

2026-07-13に確認したAWS公式情報では、次のように提供経路と運用責任が異なります。

| 比較対象 | この演習で扱う提供経路 | 接続前に確認する責任境界 |
| --- | --- | --- |
| Marketplace AWS API MCP Server | AWS Marketplaceから取得し、Amazon Bedrock AgentCore Runtimeへコンテナとしてデプロイする経路 | デプロイ、runtime、認証、session分離、実行roleの権限、ログと費用を導入側が確認する |
| managed AWS MCP Server | AWSが運用する単一のMCP endpointへ接続する経路 | IAM認証される機能の権限、利用する機能、監査、送信情報、利用量を導入側が確認する |

AWS公式のgetting startedは、AWS API MCP ServerおよびAWS Knowledge MCP Serverからmanaged AWS MCP Serverへの切り替えを推奨しています。一方、Marketplace listingが存在する事実とは分けて記録します。「後継が推奨されること」と「別の提供経路が存在すること」は同じ意味ではありません。また、AWS Marketplace MCP Serverという別の製品検索用serverを、Marketplace上のAWS API MCP Serverと混同しないでください。

確認した公式情報:

- [Managed AWS MCP Server](https://docs.aws.amazon.com/agent-toolkit/latest/userguide/mcp-server.html)
- [Get started with the managed AWS MCP Server](https://docs.aws.amazon.com/agent-toolkit/latest/userguide/getting-started-aws-mcp-server.html)
- [AWS API MCP Server - AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-lqqkwbcraxsgw)
- [AWS API MCP Server source](https://github.com/awslabs/mcp/tree/main/src/aws-api-mcp-server)

外部仕様は変わる可能性があります。実際の導入判断では、上記の公式ページを再確認し、確認日と参照URLをチェックリストへ残してください。

## セットアップ

1. このディレクトリをターミナルで開きます。
2. Pythonのバージョンを確認します。

   ```console
   python --version
   ```

3. [`templates/mcp-preconnection-checklist.md`](templates/mcp-preconnection-checklist.md) を作業用の別名でコピーします。元のテンプレートは残しておきます。
4. [`fixtures/risk-scenarios.json`](fixtures/risk-scenarios.json) を開きます。このfixtureは架空情報であり、AWS APIの実行結果ではありません。

## 演習手順

1. 評価対象として`marketplace-aws-api`または`managed-aws-mcp`のどちらか1つを選び、公式情報の再確認日とURLを記入します。
2. fixtureの各シナリオを読み、次の6分類を1行ずつ評価します。

   - `CONNECTION`: endpoint、配置先、network、利用環境、提供経路
   - `PERMISSIONS`: 認証方式、実行identity、最小権限、session分離
   - `AUDIT`: actor、時刻、API操作、session/correlation IDを追跡できる記録
   - `SENSITIVE_DATA`: 入出力、ログ、masking、保持、外部送信
   - `PROMPT_INJECTION`: 信頼できない文書やtool出力を命令として扱わない制御
   - `COST`: runtime、API、ログ等の費用担当、予算、監視、停止基準

3. 各行を次のいずれかで判定します。

   - `PASS`: 接続前要件と根拠が揃い、停止条件も定義済み
   - `REVIEW`: 人間の確認または追加情報が必要
   - `BLOCK`: 必須制御がなく、接続を開始しない

4. すべての行に、同じ分類のfixture scenario ID、owner、`YYYY-MM-DD`形式の再確認日、具体的な停止条件を記入します。公式URLは補足できますが、scenario IDの代わりにはできません。この演習ではfixtureの`expected_decision`を期待判定として使い、異なる判定に書き換えた場合は検証に失敗します。
5. 総合判定を記入します。1件でも`BLOCK`があれば`DO_NOT_CONNECT`、`BLOCK`がなくても`REVIEW`があれば`NEEDS_REVIEW`です。全件`PASS`の場合だけ`READY_FOR_APPROVAL`にできます。これは接続承認の申請準備ができたという意味であり、接続を自動承認するものではありません。
6. [`examples/completed-mcp-preconnection-checklist.md`](examples/completed-mcp-preconnection-checklist.md) と比較し、未確認事項を推測で埋めていないことを確認します。

## 検証

完成例とfixtureを検証します。

```console
python scripts/validate_checklist.py examples/completed-mcp-preconnection-checklist.md fixtures/risk-scenarios.json
```

成功時の出力は [`expected-results/validation.txt`](expected-results/validation.txt) と一致します。自分のチェックリストを検証する場合は、第1引数をそのファイルへ置き換えてください。検証スクリプトは入力ファイルを読み取るだけで変更しません。

## 期待結果

完成したチェックリストには6分類が重複なく揃い、それぞれに判定、根拠、owner、再確認日、停止条件があります。fixtureの未確定事項は`REVIEW`または`BLOCK`となり、総合判定は個別判定から機械的に導出されます。

## クリーンアップ

AWS側のcleanupは不要です。演習で作ったMarkdownのコピーだけがローカルに残ります。不要になった場合は、自分で作成したコピーであることを確認してから通常のファイル操作で整理してください。この演習の手順として自動削除は行いません。

## トラブルシューティング

- `python`が見つからない: Python 3.10以上をインストールし、PATHへ追加します。環境によっては`py -3`または`python3`を使用できます。
- `INVALID`になる: 表の分類名、判定、根拠、owner、再確認日、停止条件と総合判定を、表示されたエラー順に確認します。
- JSON errorになる: fixtureをUTF-8の正しいJSONとして保存し、末尾カンマを入れていないか確認します。
- 公式情報がfixtureと異なる: 公式情報を優先し、確認日とURLを更新したうえで`REVIEW`として責任者へ確認します。
- 検証成功なのに安全性を判断できない: 構造検証は実際のIAM、network、監査設定を検証しません。接続は行わず、組織の承認手順へ進めます。

## バージョン情報

- 教材バージョン: 1.0.0
- 検証環境: Python 3.10以上（標準ライブラリのみ）
- 公式情報の最終確認日: 2026-07-13
