# AI駆動開発ワークショップ

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/fbbp/kirinuki-workshop)

YouTube長尺動画から縦型ショート動画を自動生成するパイプラインを、Claude Codeと一緒に構築するハンズオンワークショップです。

## クイックスタート

1. 上の「Open in GitHub Codespaces」ボタンをクリック
2. 環境構築完了を待つ（数分）
3. ターミナルで `claude` を実行

詳しい手順は [docs/WORKSHOP_README.md](docs/WORKSHOP_README.md) を参照。

## ゴール

```
入力: 1時間の横型動画（16:9）
    ↓
出力: 縦型ショート動画（9:16、字幕付き）
```

## 使用技術

| 用途 | ツール |
|------|--------|
| ASR | Groq whisper-large-v3-turbo |
| LLM | Groq openai/gpt-oss-120b |
| 動画処理 | ffmpeg, moviepy |
| 日本語処理 | MeCab |
| 開発 | Claude Code |

## ドキュメント

- [CLAUDE.md](CLAUDE.md) - プロジェクト仕様書（Claude Code用）
- [docs/WORKSHOP_README.md](docs/WORKSHOP_README.md) - 参加者向け手順書
- [docs/ai-driven-dev-workshop.md](docs/ai-driven-dev-workshop.md) - リファレンス資料
