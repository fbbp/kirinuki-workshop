# YouTube Shorts Generator

## Goal

1時間の横型動画（16:9）から、縦型ショート動画（9:16、字幕付き）を自動生成するパイプラインを構築する。

## Architecture

```
入力: 1時間の横型動画 (/videos/sample.mp4)
    ↓
[1] Groq Whisper API (ASR)
    - whisper-large-v3-turbo
    - 単語レベルタイムスタンプ取得
    ↓
[2] Groq LLM (トピック分割・スコアリング)
    - openai/gpt-oss-120b
    - 15-60秒の「ショート向き」区間を特定
    - 完結性・興味度・引きでスコアリング
    ↓
[3] ffmpeg + moviepy (動画加工)
    - 縦型(9:16)にクロップ
    - ぼかし背景追加
    - 字幕オーバーレイ
    ↓
[4] MeCab (日本語字幕)
    - 単語分割
    - ハイライトアニメーション用
    ↓
出力: 複数の縦型ショート動画 (/output/*.mp4)
```

## File Structure

```
/videos/       - 入力動画（読み取り専用）
/output/       - 生成物をここに保存
/home/workshop - 作業ディレクトリ（コードはここに書く）
```

## API Keys

- `GROQ_API_KEY` - 環境変数から取得（設定済み）

## Tech Stack

| 用途 | ツール |
|------|--------|
| パッケージ管理 | uv |
| ASR | Groq whisper-large-v3-turbo |
| LLM | Groq openai/gpt-oss-120b |
| 動画処理 | ffmpeg, moviepy |
| 日本語処理 | MeCab + unidic-lite |

## Groq API Usage

### Whisper (ASR)
```python
from groq import Groq
client = Groq()

with open("video.mp4", "rb") as f:
    transcription = client.audio.transcriptions.create(
        file=f,
        model="whisper-large-v3-turbo",
        response_format="verbose_json",
        timestamp_granularities=["word", "segment"],
        language="ja"
    )
```

### LLM (gpt-oss-120b)
```python
response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3
)
```

## Constraints

- 出力は必ず `/output/` に保存すること
- 字幕は日本語、読みやすいフォントサイズ
- 縦型 (9:16) でぼかし背景を適用
- 1クリップは15-60秒を目安

## Quick Start

```bash
# 1. プロジェクト初期化
uv init shorts-generator
cd shorts-generator

# 2. 依存関係追加
uv add groq moviepy mecab-python3 unidic-lite

# 3. 開発開始
uv run python main.py
```

## Reference

`reference.md` に詳細なリファレンス資料があります。
