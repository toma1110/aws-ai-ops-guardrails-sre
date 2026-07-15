# Section 5: ReadOnly IAMガードレールをローカル検証する

この演習では、AI専用roleと追跡可能なsessionを人間用roleから分離し、ReadOnly調査に必要なactionだけをAllowし、禁止操作を明示Denyする設計packageをローカルで検証します。AWSには接続せず、policyをAWSへ適用しません。

## 到達目標

- AI専用roleと人間用roleの責任を分離し、`actor`、`ticket`、`run`を含むsession名で追跡境界を説明する
- Allow actionを承認済みのメトリクス、ログ、API監査、構成履歴の読み取りへ限定する
- IAM変更、EC2の開始・停止・終了、ログ削除などを明示Denyとして検証する
- Allow、明示Deny、暗黙Denyのケースを、同じ静的policy fixtureから再現する
- JSON構文、package schema、action populationをAWS認証情報なしで検査する

## 前提条件

- Python 3.10以上（標準ライブラリのみ）
- JSONを編集できるテキストエディタ
- PowerShell、コマンドプロンプト、または一般的なUnix shell

AWSアカウント、AWS認証情報、AWS CLI、追加のPython packageは不要です。

> **費用と安全性:** この必須演習はローカルファイルだけを読みます。AWS APIを呼ばず、IAM roleやpolicyを作成・変更・適用・削除しないため、AWS利用料金は発生しません。実際のcredential、account ID、顧客情報をfixtureへ追加しないでください。

## packageの構成

- [`examples/iam-guardrail-package/iam-policy.json`](examples/iam-guardrail-package/iam-policy.json): 完成したAllowと明示Denyのpolicy例
- [`examples/iam-guardrail-package/role-session-boundary.json`](examples/iam-guardrail-package/role-session-boundary.json): AI role、人間role、追跡可能sessionの責任境界
- [`fixtures/guardrail-requirements.json`](fixtures/guardrail-requirements.json): 許可・禁止actionの正規母集団と安全宣言
- [`fixtures/evaluation-cases.json`](fixtures/evaluation-cases.json): Allow 4件、明示Deny 3件、暗黙Deny 2件
- `tests/fixtures/`: wildcard Allow、明示Deny欠落、JSON構文エラーのnegative fixture

## 評価ルール

このローカルvalidatorは次の順で1 actionを判定します。

1. 明示Denyのpatternに一致すれば`EXPLICIT_DENY`
2. それ以外でAllow actionに一致すれば`ALLOW`
3. どちらにも一致しなければ`IMPLICIT_DENY`

この優先順位と暗黙Denyの意味は、[AWS IAM User Guideのpolicy evaluation logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic_policy-eval-denyallow.html)に合わせています。ただし、このvalidatorはこの教材のidentity-based policy 1件だけを静的評価する学習用modelです。resource-based policy、permissions boundary、session policy、SCP、RCP、condition、実request contextを含むAWSの最終認可結果は証明しません。

## 演習手順

1. このREADMEがあるディレクトリをターミナルで開き、Pythonを確認します。

   ```console
   python --version
   ```

2. `role-session-boundary.json`を開き、次を確認します。

   - `AiReadonlyInvestigationRole`と`HumanOperatorRole`が別名である
   - AI roleはReadOnly証拠収集と調査メモに限定される
   - 変更承認、IAM変更、復旧判断は人間roleの責任である
   - session例`ai-analyst-INC1234-run01`が`actor`、`ticket`、`run`を含む

3. `iam-policy.json`を開き、Allowに`*`を使わず、requirementsの11 actionだけが順番どおりにあることを確認します。`Resource: "*"`は、このfixtureが扱うaction scopeを固定したものです。resource-level条件や本番policy設計の十分性を意味しません。
4. `DenyProhibitedMutations`に7 patternがあり、`iam:*`と個別の変更・削除actionが含まれることを確認します。明示Denyは追加policyのAllowより強い禁止境界を表します。
5. `evaluation-cases.json`を読み、各actionを評価ルールで手計算します。`ec2:StopInstances`は明示Deny、`s3:GetObject`はAllowにないため暗黙Denyです。
6. 完成packageを検証します。

   ```console
   python scripts/validate_iam_guardrails.py
   ```

7. 成功出力を[`expected-results/validation.txt`](expected-results/validation.txt)と比較します。
8. templateを作業用directoryへコピーし、`REPLACE_`項目をrequirementsに合わせて編集します。検証するときは4つのpathを指定します。

   ```console
   python scripts/validate_iam_guardrails.py path/to/iam-policy.json path/to/role-session-boundary.json fixtures/evaluation-cases.json fixtures/guardrail-requirements.json
   ```

9. negative fixtureを確認します。`invalid-allow-wildcard.json`は過剰Allow、`invalid-missing-explicit-deny.json`はDeny欠落、`invalid-json-syntax.json`はJSON構文エラーとして拒否されます。

## 期待結果

完成packageは11/11 Allow action、7/7明示Deny pattern、9/9評価ケースを通過します。判定内訳は`ALLOW=4 EXPLICIT_DENY=3 IMPLICIT_DENY=2`です。AI roleと人間roleは分離され、追跡可能sessionが必須で、`aws_connection`と`policy_application`はともに`false`です。

templateやnegative fixtureは成功してはいけません。validatorが`INVALID`と具体的な理由を返すことが、fail-closed検証の期待結果です。

## この検証が証明すること・しないこと

証明するのは、ローカルJSON構文、教材schema、role名の分離、session field、Allow/Deny actionの完全一致、静的ケース判定です。AWSにpolicyを適用できること、実roleのtrust policy、resource-level制約、組織のSCP、実効権限、サービス側の最新action対応は証明しません。本番利用前には、組織のsecurity担当者が公式Service Authorization Reference、対象resource、condition、全適用policyを別途確認する必要があります。

## クリーンアップ

AWS側のクリーンアップは不要です。AWS resource、role、policy、credentialを作成・変更・適用・削除していません。ローカルで作ったコピーが不要な場合だけ、自分のコピーであることを確認して通常のファイル操作で整理してください。validatorは入力を変更せず、自動削除もしません。

## トラブルシューティング

- `python`が見つからない: Python 3.10以上をPATHへ追加します。環境によっては`py -3`または`python3`を使います。
- `cannot read ... JSON`になる: JSON末尾のcomma、閉じ括弧、引用符を確認します。`invalid-json-syntax.json`は意図的に失敗する例です。
- `Allow actions must exactly match`になる: requirementsのactionを漏れ・追加・並べ替えなしで転記します。Allowのwildcardは使いません。
- `Deny actions must exactly match`になる: 禁止actionを弱めず、7 patternすべてを順番どおりに含めます。
- `session example ... pattern`になる: `ai-<actor>-<TICKET><number>-run<number>`形式で3つの追跡fieldを含めます。
- `decision mismatch`になる: 明示Deny、Allow、暗黙Denyの順で評価し、actionの大文字小文字ではなくpattern一致を確認します。
- 文字化けする: すべてのJSONとMarkdownをUTF-8で保存します。

## バージョン情報

- 教材バージョン: 1.0.0
- fixture schema: 1
- 検証環境: Python 3.10以上（標準ライブラリのみ）
- AWS IAM評価則の公式資料確認日: 2026-07-16
