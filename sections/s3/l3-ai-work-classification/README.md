# Section 3: AI作業分類表を作る

この演習では、ローカルの12シナリオを使い、AIに任せるReadOnly調査、AIに任せないWrite操作、人間の確認が必要な判断を1枚の分類表にまとめます。AWSには接続しません。

## 到達目標

- メトリクス、ログ、構成履歴の確認と、根拠付き報告の下書きを`ALLOW`へ分類する
- 変更、release、IAM変更、削除、復旧実行を`PROHIBIT`へ分類し、AIが実行しない理由を説明する
- 本番影響の判断、機密情報、費用例外、根拠不足を`HUMAN_REVIEW`へ分類する
- 禁止規則を最優先にして、同じ条件から同じ判定を再現する

## 前提条件

- Python 3.10以上
- MarkdownとJSONを編集できるテキストエディタ
- ターミナル（PowerShell、コマンドプロンプト、または一般的なUnix shell）

AWSアカウント、AWS認証情報、MCP Server、追加のPythonパッケージは不要です。

> **費用と安全性:** この必須演習はローカルファイルを読み取るだけで、AWSへ接続しません。AWSリソース、IAM、設定、データを作成・変更・削除しないため、AWS利用料金は発生しません。認証情報や実際の顧客データをファイルへ記入しないでください。

## セットアップ

1. このREADMEがあるディレクトリをターミナルで開きます。
2. Pythonのバージョンを確認します。

   ```console
   python --version
   ```

3. [`templates/ai-work-classification.md`](templates/ai-work-classification.md) を作業用の別名でコピーします。元のテンプレートは残します。
4. [`fixtures/work-scenarios.json`](fixtures/work-scenarios.json) を開き、`local_only`が`true`、`aws_connection`と`credentials_required`が`false`であることを確認します。

## 判定ルール

上から順に適用します。先に一致した境界を優先します。

1. `PROHIBIT`: Write、release、IAM変更、削除、復旧の実行。人間レビューが必要そうに見えても、AIによる実行は禁止します。
2. `HUMAN_REVIEW`: 本番影響を伴う判断、機密情報の取扱い、費用例外、根拠不足。AIは根拠と選択肢を整理して止まります。
3. `ALLOW`: 1と2に該当せず、承認済み情報源をReadOnlyで読み、根拠を示す下書きだけを作る作業。

`HUMAN_REVIEW`はWrite操作の承認代行ではありません。たとえば復旧方針の決定は`HUMAN_REVIEW`、復旧操作の実行は`PROHIBIT`です。

## 演習手順

1. fixtureの各`task`、`observation`、`flags`を読みます。
2. 判定ルールを順に適用し、12行すべての「判定」を埋めます。
3. 判定の直接原因をfixtureの`boundary`から「境界タグ」へ転記します。
4. 各行の「根拠」に同じScenario IDと、観測内容から判断できる理由を書きます。別シナリオの根拠を流用しません。
5. 「人間の確認」には、AIが実行しないこと、確認するroleや内容を具体的に書きます。`ALLOW`でも正式送信や本番判断へ進む前の境界を書きます。
6. 監査情報と、人間へ確認するときに渡す事実、未確認事項、選択肢、判断担当roleを埋めます。
7. [`examples/completed-ai-work-classification.md`](examples/completed-ai-work-classification.md) と比較し、判定規則を説明できるか確認します。

## 期待結果

12シナリオが重複や欠落なく分類され、`ALLOW`、`HUMAN_REVIEW`、`PROHIBIT`が各4件になります。Write操作が`HUMAN_REVIEW`や`ALLOW`へ弱められず、各行が同じScenario IDの根拠へ結び付きます。

## 検証

完成例を検証します。

```console
python scripts/validate_classification.py examples/completed-ai-work-classification.md fixtures/work-scenarios.json
```

成功時の出力は [`expected-results/validation.txt`](expected-results/validation.txt) と一致します。自分の分類表を検証するときは、最初の引数だけを作業用ファイルへ置き換えます。検証スクリプトは入力ファイルを読み取るだけで、変更しません。

## クリーンアップ

AWS側のクリーンアップは不要です。AWSリソースを作成・変更・削除していません。ローカルには自分でコピーしたMarkdownだけが残るため、不要なら対象が自分のコピーであることを確認して通常のファイル操作で整理してください。検証スクリプトは自動削除を行いません。

## トラブルシューティング

- `python`が見つからない: Python 3.10以上をインストールしてPATHへ追加します。環境によっては`py -3`または`python3`を使えます。
- `decision mismatch`になる: fixtureの`flags`を見直し、禁止、要レビュー、許可の順に判定します。
- `boundary mismatch`になる: そのScenario IDの`boundary`を確認します。別シナリオのタグは使えません。
- `evidence must cite matching scenario id`になる: 各根拠欄へ同じ行のScenario IDを含めます。
- `unresolved placeholders`になる: `[...を記入]`をすべて具体的な内容へ置き換えます。
- 文字化けする: MarkdownとJSONをUTF-8で保存します。

## バージョン情報

- 教材バージョン: 1.0.0
- fixtureバージョン: 1.0.0
- 検証環境: Python 3.10以上（標準ライブラリのみ）
- 最終確認日: 2026-07-14
