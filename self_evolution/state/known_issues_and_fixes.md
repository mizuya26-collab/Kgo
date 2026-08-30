# 既知の問題と解決策

## Glob/Grep失敗問題(解決済み・2026-08-30)

### 症状
対話モードでBash/Write/Read/Editは正常動作するが、Glob/Grepを使わせようとすると失敗、または長時間待たされた末にエラーになる。

### 原因
Claude Codeが検索系の指示で内部的に呼び出す"Explore"サブエージェントが、環境変数(ANTHROPIC_MODEL)を無視して固定で claude-opus-5 (または /fast 使用時は claude-haiku-4-5) をAPIに送ってしまい、Ollama直結環境には存在しないモデルのため model_not_found エラーになっていた。

### 解決策
対話画面で `/model` を実行 → Enterで選択画面へ → gpt-oss:20b を選択。
以下のメッセージが出れば解決:
`Set model to gpt-oss:20b and saved as your default for new sessions`

settings.jsonに明示保存されることで、サブエージェント経由の呼び出しも正しいモデルを参照するようになる。

### 注意
`/fast` コマンドは組織側で無効化されているため実質機能しない。誤って触らないこと。
