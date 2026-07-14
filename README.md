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

## 動作環境

演習ごとに要件は異なります。現在収録しているローカル演習では、Python 3.10以上とMarkdownを編集できる環境を使用します。

## ライセンス

このリポジトリのライセンスは [LICENSE](LICENSE) を参照してください。
