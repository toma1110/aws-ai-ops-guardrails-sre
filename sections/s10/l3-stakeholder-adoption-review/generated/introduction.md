# Example Operations Team向け AI調査補助の導入説明

## 目的

既存運用の前段に、ReadOnlyの調査・整理・報告補助を追加する

## pilot scope

syntheticな障害情報を使うローカル評価

## 変えない既存運用

- 変更は既存のchange approvalで判断します。
- 障害対応は既存のincident responseとincident commanderの指揮を維持します。
- releaseは既存のrelease processを維持し、AIは実行しません。

## 安全境界と責任分界

- **CHANGE** — AIは調査候補と根拠を整理するだけで、変更、復旧、release、削除を実行しない（owner: change approver）
- **LOG** — synthetic dataで評価し、実運用では必要最小限の記録、masking、保持期間、外部送信境界を事前に決める（owner: security reviewer）
- **ACCOUNTABILITY** — AI出力を確定事実や承認として扱わず、根拠と不明点を添えて人間のdecision ownerへ渡す（owner: incident commander）
- **API_CONNECTION** — この演習ではAWSへ接続せず、実運用のAPI接続前にReadOnly範囲、最小権限、監査、機密情報、prompt injection、費用をreviewする（owner: security reviewer）

## 判断とreview

- decision owner: incident commander
- security owner: security reviewer
- AI出力は確定事実や承認ではなく、根拠と不明点を添えた調査補助として扱います。
