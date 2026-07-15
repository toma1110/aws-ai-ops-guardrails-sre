# ReadOnly AI調査補助アーキテクチャ

## 導入スコープ

| Scope ID | 宣言 |
| --- | --- |
| SC-01 | [INの調査範囲を記入] |
| SC-02 | [INの出力範囲を記入] |
| SC-03 | [OUTの禁止操作を記入] |
| SC-04 | [OUTの判断境界を記入] |
| SC-05 | [KEEPする既存運用を記入] |
| SC-06 | [KEEPする人間責任を記入] |

## 構成要素

| Node ID | 名称 | 境界と責任 |
| --- | --- | --- |
| HUMAN | [名称を記入] | [最終判断の責任を記入] |
| AI | [名称を記入] | [調査補助の範囲を記入] |
| MCP | [名称を記入] | [接続境界を記入] |
| IAM | [名称を記入] | [ReadOnly権限境界を記入] |
| CW | [名称を記入] | [情報源の役割を記入] |
| CT | [名称を記入] | [情報源と監査の役割を記入] |
| CFG | [名称を記入] | [情報源の役割を記入] |
| AILOG | [名称を記入] | [AI監査の役割を記入] |
| OPS | [名称を記入] | [既存運用を維持することを記入] |

## データフロー

`fixtures/architecture-requirements.json`の13フローを、同じFlow IDで1行ずつ記入します。

| Flow ID | From | To | Kind | Label |
| --- | --- | --- | --- | --- |
| F01 | [From] | [To] | [Kind] | [Label] |
| F02 | [From] | [To] | [Kind] | [Label] |
| F03 | [From] | [To] | [Kind] | [Label] |
| F04 | [From] | [To] | [Kind] | [Label] |
| F05 | [From] | [To] | [Kind] | [Label] |
| F06 | [From] | [To] | [Kind] | [Label] |
| F07 | [From] | [To] | [Kind] | [Label] |
| F08 | [From] | [To] | [Kind] | [Label] |
| F09 | [From] | [To] | [Kind] | [Label] |
| F10 | [From] | [To] | [Kind] | [Label] |
| F11 | [From] | [To] | [Kind] | [Label] |
| F12 | [From] | [To] | [Kind] | [Label] |
| F13 | [From] | [To] | [Kind] | [Label] |

## 図

上の構成要素とデータフローをMermaidで可視化してください。validatorが図と表を全数照合できるよう、最初に`NODE["名称"]`形式で9 nodeを宣言します。各edgeの直前の独立行へ`%% F01`のように対応するFlow IDを1つ書き、コメントとedgeの間に空行や別の行を入れません。通常edgeは`-->`、`audit`は`-.->`、`human_decision`は`==>`を使用します。図も検証対象であり、表と異なるnodeやedgeは追加できません。

```mermaid
flowchart LR
  HUMAN["[名称を記入]"]
  %% F01
  HUMAN -->|[Label]| AI
```

## 判断と非置換の説明

- 人間判断: [AIが止まり、人間へ渡す内容を記入]
- 既存運用: [AIが既存運用を置き換えない理由を記入]
- 監査: [CloudTrailとAI実行ログの役割の違いを記入]

## 設計記録

- 作成者role: [roleを記入]
- 作成日: [YYYY-MM-DD]
- 使用fixture: `fixtures/architecture-requirements.json`
- レビュー状態: [未確認/承認/差戻し]

