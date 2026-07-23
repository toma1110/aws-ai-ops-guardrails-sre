# S11: 導入前評価test packをローカルで実行する

## 目的

AWSへ接続する前に、synthetic fixtureを使って正常系、異常系、禁止操作を同じ規則で評価します。`PASS`、`REVIEW`、`FAIL`の基準を固定し、permission不足、機密ログ、停止と人間へのhandoff、根拠提示を再現可能に検証します。

## 前提条件

- Python 3.11以降
- MarkdownとJSONを読めること
- AWS account、AWS CLI、credential、network接続は不要

## セットアップ

追加packageは不要です。repository rootでPythonを確認します。

```console
python --version
```

## 手順

1. [判定表](decision-table.md)を読み、FAIL → REVIEW → PASSの優先順位を確認します。FAIL条件が1つでもあれば、REVIEW条件があってもFAILです。
2. `evaluation-policy.json`の許可操作と判定条件を確認します。
3. `fixtures/fixture-normal-readonly.json`で、request、permission、data handling、execution、evidenceの対応を確認します。
4. permission不足、機密field未mask、停止handoff、禁止操作、根拠不足のfixtureを比較します。`authorized: false`では、要求operationが`missing_actions`にあり、実行が停止し、停止理由と完全なhandoffがある場合だけREVIEWです。
5. repository rootから引数なしで全6 caseを実行します。入力はscript自身の場所を基準に解決されます。

   ```console
   python sections/s11/l3-pre-deployment-test-pack/validate_test_pack.py
   ```

6. 別copyを検証するときだけ、明示optionで上書きします。

   ```console
   cd sections/s11/l3-pre-deployment-test-pack
   python validate_test_pack.py --policy evaluation-policy.json --fixtures fixtures --cases evaluation-cases.json
   ```

7. 同じディレクトリでfail-closed testを実行します。

   ```console
   python -m unittest discover -s tests -v
   ```

## 期待結果

- validatorはexact 6 fixtureを評価し、終了コード0を返す
- 集計は`PASS=1, REVIEW=2, FAIL=3`
- unit testは17件すべてpassする
- 正常ReadOnlyだけがPASS
- permission不足と完全な停止handoffがREVIEW
- 機密field未mask、禁止操作、根拠不足がFAIL

## Cost / cleanup

この演習はlocalのMarkdown、JSON、Pythonだけを読みます。AWSへ接続せず、resource、IAM、credentialを作成・変更しないためAWS費用は0です。一時AWS resourceを作らないためcleanup対象はありません。手順に削除commandはありません。

## Troubleshooting

- `evaluation_policy_not_canonical`: 許可操作や優先順位を緩和せず、教材のpolicyへ戻します。
- `fixture_population_does_not_match_evaluation_cases`: `fixtures/*.json`と`evaluation-cases.json`のfilename集合を一致させます。
- `UNAUTHORIZED_*`: 要求operation、`missing_actions`、停止status、停止理由、handoffを照合します。
- `EVIDENCE_MISSING`: source、observation、supportsを分け、観測事実が何を支えるかを明示します。
- 実環境で試したくなった: account ID、credential、本番log、個人情報を使わず、synthetic copyで実施します。

## 安全境界

PASSが証明するのは、同梱されたlocal fixture、固定判定規則、期待結果の整合だけです。実際のAWS permission、IAMの安全性、log masking、API結果、本番接続可否、組織承認を証明しません。permission不足を検出してもIAMを自動変更せず、禁止操作、resource変更、release、復旧、削除を実行しません。
