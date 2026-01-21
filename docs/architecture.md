# 配信切り抜き自動化ツール - アーキテクチャ設計書

## 概要

YouTube情報番組から、YouTubeショート向けの切り抜き区間を自動選定するツール。

## 最終ゴール

```
YouTube情報番組（長尺）
        ↓
   自動処理
        ↓
ショート向き区間リスト（60秒以内 × N本）
        ↓
縦型ショート動画（9:16）
```

## 実装状況

| コンポーネント | 状態 | スクリプト |
|---------------|------|-----------|
| ASR処理 | 完了 | `transcribe.py` |
| 話題区切り（embedding版） | 完了 | `segment.py` |
| 話題区切り（Claude版） | 完了 | `segment-with-claude.py` |
| スコアリング（embedding版） | 完了 | `score.py` |
| スコアリング（Claude版） | 完了 | `score-with-claude.py` |
| 統合パイプライン | 完了 | `pipeline.py`, `pipeline-claude.py` |
| 縦型動画生成 | 完了 | `shorts_generator.py` |
| Hormozi風字幕 | 完了 | `hormozi_captions.py` |
| VLM拡張 | 未着手 | - |

---

## アーキテクチャ

### 処理パイプライン

```
┌─────────────────────────────────────────────────────┐
│ 1. 素材分解                                          │
│    動画 → ffmpeg → 音声（180秒チャンク分割）         │
│    スクリプト: transcribe.py                         │
└─────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────┐
│ 2. 音声認識（ASR）                                   │
│    Parakeet MLX (nvidia/parakeet-tdt_ctc-0.6b-ja)   │
│    → テキスト + タイムスタンプ（文・トークン単位）   │
│    出力: {video}.json                                │
└─────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────┐
│ 3. 話題区切り検出                                    │
│    - 大セグメント: embedding類似度（閾値0.3）        │
│    - 小セグメント: Claude Code（15-90秒単位）        │
│    → 階層的に話題区間を検出                          │
│    スクリプト: segment.py / segment-with-claude.py   │
│    出力: {video}-segments.json / -segments-claude.json │
└─────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────┐
│ 4. 区間スコアリング                                  │
│    Claude Code でショート適性を評価（1-10点）        │
│    - 完結性: 単体で意味が通るか                      │
│    - 興味度: 視聴者の関心を引くか                    │
│    - 引き: 強いオープニングフックがあるか            │
│    スクリプト: score.py / score-with-claude.py       │
│    出力: {video}-scores.json / -scores-claude.json   │
└─────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────┐
│ 5. 候補選定                                          │
│    スコア閾値でフィルタリング → clips.json           │
│    [{start, end, score, topic, hook, ...}, ...]     │
└─────────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────────┐
│ 6. 動画生成                                          │
│    shorts_generator.py:                              │
│      - 縦型9:16（1080x1920）                         │
│      - 背景ぼかし + チャンネル名バッジ               │
│      - MeCabで単語分割 → 字幕表示                    │
│    hormozi_captions.py:                              │
│      - 単語ハイライト（黄色）                        │
│      - バウンスエフェクト                            │
└─────────────────────────────────────────────────────┘
```

---

## スクリプト構成

```
scripts/
├── transcribe.py             # ASR処理（Parakeet MLX）
├── transcribe.sh             # ASRシェルラッパー
├── segment.py                # 話題区切り（embedding類似度）
├── segment-with-claude.py    # 話題区切り（Claude版・推奨）
├── score.py                  # スコアリング（embedding版）
├── score-with-claude.py      # スコアリング（Claude版・推奨）
├── pipeline.py               # 統合パイプライン（embedding版）
├── pipeline-claude.py        # 統合パイプライン（Claude版・推奨）
├── shorts_generator.py       # 縦型動画生成（9:16）
└── hormozi_captions.py       # Hormozi風アニメ字幕
```

---

## 使用モデル

| 用途 | モデル | 実行環境 | メモリ使用量 |
|------|--------|----------|-------------|
| ASR | nvidia/parakeet-tdt_ctc-0.6b-ja | MLX（ローカル） | ~2GB |
| 話題区切り（embedding） | paraphrase-multilingual-MiniLM-L12-v2 | MLX変換済み（ローカル） | ~100MB |
| 話題区切り・スコアリング | Claude | Claude Code CLI | - |
| 形態素解析 | MeCab + unidic-lite | ローカル | ~50MB |

---

## データフロー詳細

### ASR出力 (`{video}.json`)

```json
{
  "source": "video.mp4",
  "duration": 3600,
  "chunk_size": 180,
  "sentences": [
    {
      "text": "今日は特集をお届けします",
      "start": 0.5,
      "end": 2.3,
      "tokens": [
        {"text": "今日", "start": 0.5, "end": 0.8},
        {"text": "は", "start": 0.8, "end": 0.9},
        ...
      ]
    }
  ]
}
```

### セグメント出力 (`{video}-segments-claude.json`)

```json
{
  "source": "output/video.json",
  "method": "claude",
  "large_threshold": 0.3,
  "claude_model": "claude-opus-4-5-20251101",
  "total_large_segments": 18,
  "total_small_segments": 66,
  "segments": [
    {
      "large_segment_index": 0,
      "start": 282,
      "end": 318,
      "duration": 36,
      "topic": "福岡・後継ぎ会訪問"
    }
  ]
}
```

### スコア出力 (`{video}-scores-claude.json`)

```json
{
  "source": "output/video.json",
  "model": "claude-opus-4-5-20251101",
  "total_segments": 66,
  "scored_segments": 62,
  "results": [
    {
      "score": 7,
      "clip_start": "36:42",
      "clip_end": "37:20",
      "topic": "父の研究と挑戦",
      "hook": "「できない」と言われ続けた父の",
      "reason": "..."
    }
  ]
}
```

---

## 話題区切り検出の仕組み

### 階層的アプローチ

1. **大セグメント**: embedding類似度で話題の大枠を検出（閾値0.3）
2. **小セグメント**: 各大セグメント内でClaudeが15-90秒単位に分割
3. **偽陰性を避ける方針**: 多めに候補を出し、スコアリングで選別

### Embedding類似度計算

MLX Embeddingsは文をベクトル（384次元）に変換。
隣接するセグメント間のコサイン類似度を計算し、
閾値以下（話題が変わった）ポイントを区切りとして検出。

```python
from mlx_embeddings import load
import numpy as np

model, tokenizer = load("models/paraphrase-multilingual-MiniLM-L12-v2-mlx")

# ASR出力（チャンクごとのテキスト）
segments = [
    {"start": 0, "text": "今日はAPEXやっていきます"},
    {"start": 30, "text": "ランクマッチ行くぞ"},
    {"start": 300, "text": "じゃあスパチャ読んでいきます"},
]

# ベクトル化
embeddings = model.encode([s["text"] for s in segments], tokenizer)

# 隣接セグメント間のコサイン類似度
for i in range(1, len(embeddings)):
    sim = np.dot(embeddings[i-1], embeddings[i]) / (
        np.linalg.norm(embeddings[i-1]) * np.linalg.norm(embeddings[i])
    )
    if sim < 0.3:  # 閾値以下なら話題切り替わり
        print(f"話題変化: {segments[i]['start']}秒")
```

---

## 動画生成の仕組み

### shorts_generator.py

縦型9:16（1080x1920）のショート動画を生成。

**レイアウト構成:**
```
┌────────────────────┐
│  [チャンネル名]     │ ← 上部8%: バッジスタイル
│                    │
│   概要テキスト      │ ← 上部18%: 黄色+アウトライン
│                    │
│  ┌──────────────┐  │
│  │              │  │
│  │   元動画     │  │ ← 中央: 幅85%、縦横比維持
│  │  (16:9等)    │  │
│  │              │  │
│  └──────────────┘  │
│                    │
│   字幕テキスト      │ ← 下部78%: Hormozi風
│  (単語ハイライト)   │
│                    │
└────────────────────┘
背景: 元動画をぼかし+暗く
```

**字幕処理フロー:**
1. ASRトークン（文字単位）を取得
2. MeCabで形態素解析 → 単語単位にマージ
3. 助詞・助動詞を前の単語に結合
4. 5単語ごとにグループ化
5. 現在単語を黄色ハイライト + バウンスエフェクト

---

## 技術的詳細

### メモリ管理

- **MLX**: `mx.clear_cache()` + `gc.collect()` をバッチ処理ごとに実行
- **ASR処理**: 180秒チャンクで分割処理（長時間動画対応）
- **動画処理**: MoviePyでフレーム単位処理

### Claude Code呼び出しパターン

```python
proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    start_new_session=True  # 独立プロセスグループ
)
try:
    stdout, stderr = proc.communicate(timeout=90)
except subprocess.TimeoutExpired:
    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
finally:
    if proc.poll() is None:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    proc.wait()
    gc.collect()
```

---

## ベンチマーク結果

### 60分動画テスト（Claude版）

| 項目 | 値 |
|------|-----|
| 入力動画 | 60分（情報番組） |
| 大セグメント | 18 |
| 小セグメント | 66 |
| スコア済み | 62 |
| 最高スコア | 7点 |
| 処理時間 | 約25分 |

### 上位候補サンプル

| 点数 | 区間 | 話題 | フック |
|------|------|------|--------|
| 7 | 36:42-37:20 | 父の研究と挑戦 | 「できない」と言われ続けた父の |
| 6 | 07:40-08:12 | 仲間との交流不足 | ファイナリストに陰口言われてた |
| 6 | 30:22-30:45 | 社名とメッキ誤解 | 家業がメッキだと思ってたら… |
| 6 | 37:35-38:00 | 苦難と地域の支援 | 地域の町工場が支えてくれた |

---

## コスト見積もり

### ローカル実行（Apple Silicon）

- ASR (Parakeet MLX): 統合メモリ使用、180秒チャンクで安定動作
- Embeddings (MiniLM-L12 MLX): ~100MB、高速処理
- Claude Code: サブスクリプション内で利用

### OpenRouter (VLM使用時・将来)

| サンプリング | フレーム数/1h | 料金 |
|-------------|-------------|------|
| 0.1fps (10秒毎) | 360枚 | $0 (無料枠) |
| 1fps (毎秒) | 3,600枚 | $0 (無料枠) |

---

## 将来拡張: VLM

将来的にVLMを追加する場合：

- **モデル**: allenai/Molmo2-8B
- **API**: OpenRouter (無料枠)
- **用途**: コーナータイトル/テロップ検出（補助）

### VLM使用時のプロンプト例

```
あなたは情報番組の話題区切りを検出するアシスタントです。

以下を検出してください：
- コーナータイトル/見出しテロップの出現
- 大きなシーン転換（VTR↔スタジオ）

以下は無視してください：
- 画面隅のワイプ（出演者の小窓）の変化
- 同一シーン内のカメラアングル変化

出力形式：
{"change": true, "type": "コーナータイトル", "text": "○○特集"}
```

---

## 技術メモ

### 量子化の精度劣化

| モデルタイプ | 4bit劣化 | 8bit劣化 |
|-------------|---------|---------|
| Text Generation (LLM) | 1-3% | ほぼなし |
| Image-Text (VLM) | 5-10% | 2-5% |
| Video-Text (VLM) | 7-15%+ | 3-7% |

### 情報番組の特性

- ワイプ（小窓）が四隅に出る → VLM使用時はプロンプトで無視指示
- カメラ切り替え ≠ 話題切り替え → ASRベースの方が確実

---

## 今後の改善点

### 優先度高

1. **閾値チューニング** - 大セグメント閾値の最適化
2. **プロンプト改善** - スコアリング精度向上

### 将来

3. **VLM拡張** - 画面変化検出（Molmo等）
4. **バッチ処理** - 複数動画の一括処理
5. **Web UI** - ブラウザからの操作
