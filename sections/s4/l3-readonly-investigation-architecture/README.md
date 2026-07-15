# Section 4: ReadOnly AI調査補助アーキテクチャを作る

この演習では、AI、MCP、IAM、CloudWatch、CloudTrail、AWS Config、AI実行ログ、人間判断、既存運用を1枚のReadOnly調査補助アーキテクチャへ配置します。Section 1で定義した導入スコープと同じ境界を表へ明記し、図とデータフローがその境界を破っていないことをローカルvalidatorで確認します。AWSには接続しません。

## 到達目標

- 調査依頼からReadOnly情報収集、根拠提示、人間判断までのデータフローを可視化する
- MCPを接続経路、AI専用ReadOnly IAMを権限の主制御として分ける
- CloudTrailのAWS API監査とAI実行ログのAI処理監査を別経路で示す
- AIから既存運用への直接経路を作らず、人間の最終判断を必須にする
- 既存の障害対応、承認、変更、release手順を置き換えないと説明する

## 前提条件

- Python 3.10以上（標準ライブラリのみ）
- MarkdownとJSONをUTF-8で編集できるテキストエディタ
- Mermaidを表示できるエディタは任意。通常の内容検証にMermaid CLIや追加packageは不要

AWSアカウント、AWS認証情報、MCP Server、AWS CLIは不要です。

> **費用と安全性:** 必須演習はローカルのMarkdownとJSONを読み取るだけです。AWS APIへ接続せず、IAM policyを適用せず、AWSリソースや既存運用を作成・変更・削除しないため、AWS利用料金は発生しません。実在するaccount ID、認証情報、顧客データを教材へ記入しないでください。

## セットアップ

1. このREADMEがあるディレクトリをターミナルで開きます。
2. `python --version`を実行し、Python 3.10以上を確認します。
3. [`templates/readonly-investigation-architecture.md`](templates/readonly-investigation-architecture.md) を作業用の別名でコピーします。
4. [`fixtures/architecture-requirements.json`](fixtures/architecture-requirements.json) を開き、`local_only`が`true`、`aws_connection`と`credentials_required`が`false`であることを確認します。

## 演習手順

1. 導入スコープ表の`SC-01`から`SC-06`をfixtureと一致させます。`IN`はReadOnly調査と根拠付き下書き、`OUT`は変更・release・IAM変更・削除・自動復旧と本番判断、`KEEP`は既存運用と人間責任です。
2. 9つのNode IDを表へ配置します。`MCP`は接続経路、`IAM`はAI専用ReadOnly権限境界、`CW`・`CT`・`CFG`は異なるAWS情報源です。
3. fixtureの`F01`から`F13`をデータフロー表へ転記します。Flow ID、From、To、Kind、Labelは証拠を結び付けるため変更しません。
4. Mermaid図を作り、表と同じ構成を可視化します。9 nodeは`NODE["名称"]`形式で宣言します。各edgeの直前の独立行へ対応する`%% Flow ID`を1つ書き、コメントとedgeを隣接させます。行末コメントにはしません。通常edgeは`-->`、監査edgeは`-.->`、人間判断edgeは`==>`です。`AI -> OPS`の直接経路は作りません。既存運用へ接続できるのは`HUMAN -> OPS`の`human_decision`だけです。
5. `F10`でMCP経由AWS APIアクセスをCloudTrailへ、`F11`でAIの入力・出力・根拠・実行IDをAI実行ログへ記録します。両者を代用関係にしません。
6. 「判断と非置換の説明」に、AIが止まる地点、人間へ渡す内容、既存運用を維持する理由、2つの監査経路の違いを書きます。
7. [`examples/completed-readonly-investigation-architecture.md`](examples/completed-readonly-investigation-architecture.md) と比較し、図の各要素をスコープ表とFlow IDへ逆引きできることを確認します。

## 期待結果

スコープ6件、構成要素9件、フロー13件が検証されます。ReadOnly権限境界、CloudTrailとAI実行ログの2監査経路、人間判断だけが既存運用へ接続することが明示され、未入力欄は0件になります。

## 検証

```console
python scripts/validate_architecture.py examples/completed-readonly-investigation-architecture.md fixtures/architecture-requirements.json
```

成功出力は [`expected-results/validation.txt`](expected-results/validation.txt) と一致します。自分の図を検証するときは第1引数だけを作業用Markdownへ置き換えます。validatorは入力を読み取るだけで、ファイルやAWS環境を変更しません。

追加の実レンダーsmoke checkは、Node.js 20以上とChromeまたはEdgeがあるローカル環境で次を実行します。固定版`@mermaid-js/mermaid-cli@11.12.0`を一時cacheへ取得し、完成例のMermaidをSVGへ実際にparse/renderした後、一時ファイルを削除します。初回取得だけnpm registryへの接続が必要で、AWSには接続しません。

```console
python scripts/render_mermaid_smoke.py examples/completed-readonly-investigation-architecture.md
```

旧記法の回帰fixture `tests/fixtures/invalid-inline-flow-id-comment.md` は同じコマンドでexit 1になり、Mermaid parserの構文エラーを再現します。

## クリーンアップ

AWS側のクリーンアップは不要です。AWSへ接続せず、リソース、IAM、設定、データを作成・変更・削除していません。ローカルには自分で作ったMarkdownコピーだけが残ります。不要な場合は対象が自分のコピーであることを確認し、通常のファイル操作で整理してください。validatorは自動削除しません。

## トラブルシューティング

- `python`が見つからない: Python 3.10以上をPATHへ追加します。環境によっては`py -3`または`python3`を使用します。
- `scope mismatch`になる: Scope IDの文をfixtureと比較し、`IN`、`OUT`、`KEEP`の境界を弱めていないか確認します。
- `flow ... mismatch`になる: 同じFlow IDのFrom、To、Kind、Labelをfixtureと一致させます。
- `Mermaid edge is missing a preceding Flow ID comment`になる: edge直前の独立行へ対応する`%% Fxx`を1つ追加します。
- `Flow ID comment ...`になる: Flow IDコメントとedgeの間の空行・node・別コメントを除き、1コメントと1edgeを隣接させます。
- `AI must not connect directly to existing operations`になる: `AI -> OPS`を削除し、判断を`AI -> HUMAN -> OPS`へ戻します。
- `missing flow row: F10`または`F11`になる: CloudTrailとAI実行ログを別々の監査経路として追加します。
- `unresolved placeholders`になる: `[...を記入]`と日付・レビュー状態の未入力欄を具体化します。
- Mermaidを表示できない: 通常の演習では図のレンダリングは任意です。validatorはMermaid内のnode宣言と、直前の独立コメントでFlow IDを結び付けたedgeを表・fixtureと全数照合します。必要に応じて上記smoke checkで実レンダーも確認します。
- 文字化けする: MarkdownとJSONをUTF-8で保存します。

## バージョン情報

- 教材・fixtureバージョン: 1.0.0
- 検証環境: Python 3.10以上（標準ライブラリのみ）
- 最終確認日: 2026-07-15
