# AI作業分類表（完成例）

## 判定規則

1. Write、release、IAM変更、削除、復旧の実行は、他の条件にかかわらず `PROHIBIT` とする。
2. 本番影響の判断、機密情報、費用例外、根拠不足を含む場合は `HUMAN_REVIEW` とする。
3. 上記に該当せず、承認済み情報源をReadOnlyで読み、根拠付きの下書きだけを作る場合は `ALLOW` とする。

## 分類結果

| Scenario ID | 作業 | 判定 | 境界タグ | 根拠 | 人間の確認 |
| --- | --- | --- | --- | --- | --- |
| METRICS-01 | 承認済みのメトリクスfixtureから異常時刻を抽出する | ALLOW | READ_APPROVED | METRICS-01はローカルの承認済み情報源を読むだけで、出力も根拠付きメモに限定される | 不要。ただし出力を本番判断として扱わない |
| LOGS-01 | mask済みの承認済みログfixtureからエラー行を検索する | ALLOW | READ_APPROVED | LOGS-01はmask済みfixtureのReadOnly検索であり、出典行を保持する | 不要。ただしmask漏れを見つけたら作業を止める |
| CONFIG-01 | 承認済みの構成履歴fixtureを時系列に並べる | ALLOW | READ_APPROVED | CONFIG-01は観測済み履歴の整理だけで構成を変更しない | 不要。事実と推測を分けて表示する |
| REPORT-01 | 根拠IDを引用して障害報告の下書きを作る | ALLOW | EVIDENCE_DRAFT | REPORT-01は根拠ID付き下書きの作成だけで原因確定や送信をしない | 正式報告として送信する前に担当者が内容を確認する |
| CHANGE-01 | 本番アラームのしきい値を変更する | PROHIBIT | MUTATION | CHANGE-01は本番設定を書き換えるためReadOnly境界外である | AIは実行しない。変更管理手順を人間が別途開始する |
| RELEASE-01 | 修正版を本番環境へリリースする | PROHIBIT | RELEASE | RELEASE-01は本番へのWrite操作でありAIへ委任しない | AIは実行しない。承認済みrelease手順を人間が担当する |
| IAM-01 | 調査用roleへ追加ポリシーをattachする | PROHIBIT | IAM_CHANGE | IAM-01は権限境界を変えるIAM操作である | AIは実行しない。securityとIAM ownerが別工程で審査する |
| DELETE-01 | 古いロググループを削除する | PROHIBIT | DELETE | DELETE-01は監査データを不可逆に失う可能性がある | AIは実行しない。保持要件と削除承認を人間が確認する |
| RECOVERY-01 | 観測結果を基にrollbackか再起動かを決定する | HUMAN_REVIEW | IMPACT_DECISION | RECOVERY-01は本番影響を伴う復旧方針の決定である | incident commanderが根拠、選択肢、rollback可能性を確認する |
| SENSITIVE-01 | maskされていない顧客識別子を含むログの調査可否を決める | HUMAN_REVIEW | SENSITIVE_DATA | SENSITIVE-01は機密情報の取扱範囲とmasking承認が未確認である | data ownerとsecurityが利用範囲とmasking方法を決める |
| COST-01 | 承認済み上限を超えるログ調査を続けるか決める | HUMAN_REVIEW | COST_EXCEPTION | COST-01は追加費用の見積りとowner承認がない | 費用ownerが上限、期間、停止基準を確認する |
| UNCERTAIN-01 | 単一のエラー行だけで根本原因を確定する | HUMAN_REVIEW | INSUFFICIENT_EVIDENCE | UNCERTAIN-01は相関情報がなく原因確定の根拠が不足している | incident commanderが追加調査か未確定報告かを選ぶ |

## 監査情報

- 分類担当role: SRE learner
- 分類日: 2026-07-14
- 使用fixture: `fixtures/work-scenarios.json`
- 承認状態: 未確認

## 人間へ確認するときの情報

- 対象Scenario ID: RECOVERY-01
- 観測済みの事実: AIは候補と根拠を整理したが復旧操作は実行していない
- 未確認事項: 各選択肢の本番影響とrollback可能性
- 選択肢と影響: rollbackまたは再起動。どちらもサービス影響を人間が評価する
- 判断担当role: incident commander
