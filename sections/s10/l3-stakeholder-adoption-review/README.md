# S10: 現場導入の説明・FAQ・security reviewをローカル検証する

## 目的

AIを既存運用の置き換えではなくReadOnlyの調査補助として説明し、operationsとsecurityの懸念を構造化します。変更、ログ、誤回答責任、API接続の4懸念、既存の承認・障害対応・releaseを維持する境界、担当者ごとの責任、security reviewの判定と根拠を1つの資料にまとめます。

## 前提条件

- Python 3.11以降
- MarkdownとJSONを編集できること
- AWS account、AWS CLI、credential、network接続は不要

## セットアップ

追加packageは不要です。このディレクトリへ移動し、Pythonを確認します。

```console
python --version
```

## 手順

1. `introduction-template.md`を使い、対象、調査補助の範囲、既存運用を維持すること、禁止操作、停止・引き継ぎ先を説明します。
2. `faq-template.md`で、変更、ログ、誤回答責任、API接続の4懸念へ、control、確認根拠、責任者を対応付けます。
3. `security-review-checklist.md`で、scope、identity/permission、data/log、prompt injection、audit、human approval、incident/exitの7観点を`pass`、`review`、`fail`のいずれかで判定します。空欄や推測を`pass`にせず、根拠とownerを記録します。
4. `fixtures/fixture-complete.json`を自組織向けのcopyとして扱い、固有名詞や実データを入れずに各fieldの関係を確認します。教材fixture自体は変更しません。
5. `stakeholder-input.json`から3資料を決定的に再生成し、template、入力、生成結果の一致を検証します。

   ```console
   python build_materials.py --input stakeholder-input.json --templates templates --output generated
   python validate_package.py --input stakeholder-input.json --templates templates --output generated --expected expected-results.json
   ```

6. fixture母集団と期待結果を検証します。

   ```console
   python validate_adoption_package.py --fixtures fixtures --expected expected-results.json
   ```

7. fail-closed testを実行します。

   ```console
   python -m unittest discover -s tests -v
   ```

## 期待結果

- validatorは3 fixtureを検査し、`PASS: 3 packages matched expected results`と終了コード0を返す
- generatorは3資料を再生成し、package validatorは4懸念と3つの既存process維持を確認する
- 完成例1件は`READY_FOR_STAKEHOLDER_REVIEW`
- 4懸念の欠落例と既存運用を置換する例は`INVALID_PACKAGE`
- unit testは16件すべてpassし、責任分界、security review母集団、空の根拠、unsafeな変更・承認・API安全性の主張をfail closedで検出する

## Cost / cleanup

この演習はlocalのMarkdownとsynthetic JSONだけを読みます。AWSへ接続せず、resourceやcredentialを作成・変更しないためAWS費用は0です。一時resourceを作らないためcleanup対象はありません。削除commandも実行しません。

## Troubleshooting

- `fixture population does not exactly match expected results`: `fixtures/*.json`と`expected-results.json`のfilename集合を一致させます。
- `concern_ids_invalid`: 4懸念を重複なくすべて記載します。
- `preserved_processes_invalid`: `approval`、`incident_response`、`release`を維持し、AIで置換しないことを確認します。
- `review_check_ids_invalid`: 7つのsecurity review観点を重複なく記載します。
- `evidence_missing`: `pass`を推測で付けず、確認できる資料の種類とownerを記載します。実証できない場合は`review`または`fail`にします。
- 実環境情報を使いたくなった: account ID、credential、本番ログ、個人情報を入れず、syntheticなcopyで演習します。

## 安全境界

local validationが証明するのは、資料の必須項目、列挙値、母集団、相互関係だけです。AWS API接続、安全なIAM、実ログのマスキング、製品の正確性、組織の承認、責任者の受諾を証明しません。実導入では各根拠をsystem owner、security、operations、release ownerが確認し、変更・release・復旧・IAM変更・削除をAIへ委任しないでください。
