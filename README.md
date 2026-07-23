# AWS運用におけるAI活用のガードレール設計

このリポジトリには、コースで使用する演習教材、テンプレート、完成例、ローカル検証スクリプトを収録しています。AWS運用へAIを導入するときに、ReadOnlyを出発点として、権限・監査・人間の判断範囲を段階的に設計します。

## 教材の使い方

各演習は `sections/` 以下にSection・Lecture単位で配置しています。受講中のLectureに対応するREADMEを開き、その前提条件、手順、期待結果、検証方法に従ってください。

演習用ファイルには、実在するAWSアカウントID、認証情報、個人情報、実際の本番ログを記入しないでください。費用やAWS接続の有無は、各演習のREADMEで確認してください。

## 教材目次

### Section 1: なぜSREにAI運用導入力が必要なのか

- Lecture 1・2: 概念解説（リポジトリ教材なし）
- [Lecture 3: ReadOnlyから始める安全境界](sections/s1/l3-readonly-adoption-scope/README.md) — AI運用導入スコープ表を作成し、ローカルで検証します。

### Section 2: 2つのAWS MCP提供経路を実画面と公式情報で比較する

- Lecture 1・2: 概念解説（リポジトリ教材なし）
- [Lecture 3: 両方に共通する接続前リスク評価を作る](sections/s2/l3-mcp-preconnection-checklist/README.md) — 6分類のMCP接続前チェックリストをローカルfixtureで検証します。

### Section 3: AIに任せる作業・任せない作業

- Lecture 1・2: 概念解説（リポジトリ教材なし）
- [Lecture 3: AI作業分類表を完成させる](sections/s3/l3-ai-work-classification/README.md) — ReadOnly調査、禁止操作、人間確認が必要な判断を12件のローカルシナリオで分類します。

### Section 4: ReadOnly導入の全体アーキテクチャ

- Lecture 1・2: 概念解説（リポジトリ教材なし）
- [Lecture 3: ReadOnlyアーキテクチャ図を作る](sections/s4/l3-readonly-investigation-architecture/README.md) — 既存運用を置き換えないReadOnly調査補助アーキテクチャを作り、図とスコープ表の整合をローカルで検証します。

### Section 5: IAMガードレール設計

- Lecture 1・2: 概念解説（リポジトリ教材なし）
- [Lecture 3: ReadOnly IAMポリシー例を検証する](sections/s5/l3-readonly-iam-guardrails/README.md) — AI専用roleと追跡可能なsessionを分離し、最小権限のAllowと明示Denyを含むIAM policy fixtureをAWSへ適用せずローカルで検証します。

### Section 6: CloudTrailでAIのAWSアクセスを追跡する

- Lecture 1・2: 概念解説（リポジトリ教材なし）
- [Lecture 3: 監査クエリとチェックリストを試す](sections/s6/l3-cloudtrail-audit/README.md) — 合成CloudTrail eventをAI実行ID・session・ticket IDへ相関し、5つの監査項目と期待結果をローカルで検証します。

### Section 7: CloudWatch・Logs・Configを使った調査補助

- Lecture 1・2: 概念解説（リポジトリ教材なし）
- [Lecture 3: 根拠付き障害調査レポートを作る](sections/s7/l3-incident-investigation/README.md) — 合成メトリクス、ログ、変更履歴、resource状態をUTC時系列で関連付け、事実・仮説・不明点・人間判断を分離した調査結果をローカルで検証します。

### Section 8: ログ保存と説明責任

- Lecture 1・2: 概念解説（リポジトリ教材なし）
- [Lecture 3: AI実行ログJSONを検証する](sections/s8/l3-ai-execution-log-validation/README.md) — CloudTrail API監査とAI実行ログの役割を分け、相関情報、保持、マスキング、外部送信境界を9件のローカルfixtureと11件のunit testで検証します。

### Section 9: 人間判断と停止条件

- Lecture 1・2: 概念解説（リポジトリ教材なし）
- [Lecture 3: 停止条件と引き継ぎを試す](sections/s9/l3-human-decision-handoff/README.md) — 本番影響、費用、例外、権限変更、rollbackの境界を7件のローカルfixtureで判定し、`NEED_HUMAN_DECISION` の引き継ぎを検証します。

### Section 10: 現場反発を抑える導入設計

- Lecture 1・2: 概念解説（リポジトリ教材なし）
- [Lecture 3: 導入説明とreview資料を作る](sections/s10/l3-stakeholder-adoption-review/README.md) — 変更、ログ、誤回答責任、API接続の懸念と、既存運用を維持する責任分界を説明・FAQ・security review資料として作り、ローカルで検証します。

### Section 11: 導入前評価テスト

- Lecture 1: 概念解説（リポジトリ教材なし）
- [Lecture 2・3: 正常系・異常系・禁止操作を試験し、導入前test packを完成させる](sections/s11/l3-pre-deployment-test-pack/README.md) — permission不足、機密ログ、停止handoff、根拠提示を6件のsynthetic fixtureと17件のunit testで検証します。

## 動作環境

演習ごとに要件は異なります。現在収録しているローカル演習では、Python 3.10以上とMarkdownを編集できる環境を使用します。

## ライセンス

このリポジトリのライセンスは [LICENSE](LICENSE) を参照してください。
