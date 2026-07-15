# Invalid Mermaid regression fixture

This fixture preserves the former edge-line Flow ID comment that Mermaid rejects.

```mermaid
flowchart LR
  HUMAN["人間の運用担当者"]
  AI["AI調査補助"]
  HUMAN -->|承認済み調査依頼| AI %% F01
```

