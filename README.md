# kirinuki - 配信切り抜き自動化ツール

YouTube情報番組から、YouTubeショート（15-60秒）向けの切り抜き区間を自動選定するツール。

## 特徴

- **ローカルASR**: Parakeet MLX による日本語音声認識
- **階層的話題検出**: Embedding類似度 + Claude による話題区切り
- **AI スコアリング**: Claude で「ショート適性」を自動評価
- **縦型動画生成**: 9:16ショート形式 + Hormozi風アニメ字幕
- **Apple Silicon最適化**: MLXベースでローカル完結

## 処理フロー

```
動画ファイル (.mp4)
    ↓
[1] ASR処理（Parakeet MLX）
    ↓
[2] 大セグメント検出（embedding類似度）
    ↓
[3] 小セグメント検出（Claude）
    ↓
[4] スコアリング（Claude）
    ↓
[5] 動画生成（縦型9:16 + 字幕）
```

## 必要環境

- macOS (Apple Silicon推奨)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) パッケージマネージャ
- [Claude Code](https://github.com/anthropics/claude-code) (スコアリング用)

## セットアップ

```bash
cd kirinuki
uv sync
```

## 使い方

### 統合パイプライン（推奨）

```bash
# Claude版（高精度）
uv run python scripts/pipeline-claude.py video.mp4

# embedding版（高速）
uv run python scripts/pipeline.py video.mp4
```

### 個別実行

```bash
# 1. ASR処理
uv run python scripts/transcribe.py video.mp4 -o output -c 180

# 2. 話題区切り検出（Claude版）
uv run python scripts/segment-with-claude.py output/video.json

# 3. スコアリング（Claude版）
uv run python scripts/score-with-claude.py output/video-segments-claude.json
```

### 動画生成

```bash
# 縦型ショート動画（9:16）
uv run python scripts/shorts_generator.py output/clip.mp4 \
  --asr output/clip.json \
  --channel "チャンネル名"

# Hormozi風アニメ字幕
uv run python scripts/hormozi_captions.py \
  output/clip.mp4 output/clip.json -o output/clip-hormozi.mp4
```

## ディレクトリ構成

```
kirinuki/
├── scripts/
│   ├── transcribe.py         # ASR処理
│   ├── segment.py            # 話題区切り（embedding版）
│   ├── segment-with-claude.py # 話題区切り（Claude版）
│   ├── score.py              # スコアリング（embedding版）
│   ├── score-with-claude.py  # スコアリング（Claude版）
│   ├── pipeline.py           # 統合パイプライン（embedding版）
│   ├── pipeline-claude.py    # 統合パイプライン（Claude版）
│   ├── shorts_generator.py   # 縦型動画生成
│   └── hormozi_captions.py   # アニメ字幕
├── models/                   # MLX変換済みモデル
├── output/                   # 処理結果
└── docs/
    ├── architecture.md       # 設計ドキュメント
    └── handson.md            # ハンズオン資料
```

## 使用モデル

| 用途 | モデル | 実行環境 |
|------|--------|----------|
| ASR | nvidia/parakeet-tdt_ctc-0.6b-ja | MLX（ローカル） |
| Embedding | paraphrase-multilingual-MiniLM-L12-v2 | MLX（ローカル） |
| セグメント・スコアリング | Claude | Claude Code |

## スコアリング基準

- **完結性**: 単体で意味が通るか
- **興味度**: 視聴者の関心を引くか
- **引き**: 強いオープニングフックがあるか

## ライセンス

Private
