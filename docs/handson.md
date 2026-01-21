# 配信切り抜き自動化ツール - ハンズオン引き継ぎ資料

## プロジェクト概要

YouTube情報番組から、YouTubeショート（15-60秒）向けの切り抜き区間を自動選定するツール。

## 現在の進捗状況

### 完了済み

1. **ASR処理** → `scripts/transcribe.py`
2. **話題区切り検出（embedding版）** → `scripts/segment.py`
3. **話題区切り検出（Claude版）** → `scripts/segment-with-claude.py`
4. **スコアリング（embedding版）** → `scripts/score.py`
5. **スコアリング（Claude版）** → `scripts/score-with-claude.py`
6. **統合パイプライン（embedding版）** → `scripts/pipeline.py`
7. **統合パイプライン（Claude版）** → `scripts/pipeline-claude.py`
8. **MLXモデル変換** → `models/paraphrase-multilingual-MiniLM-L12-v2-mlx`
9. **縦型動画生成** → `scripts/shorts_generator.py`
10. **Hormozi風字幕** → `scripts/hormozi_captions.py`

### 未着手

1. **VLM拡張**（画面変化検出・Molmo等）

---

## ファイル構成

```
/Users/washi/workspace/kirinuki/
├── info-program.mp4              # テスト用動画（60分）
├── pyproject.toml                # uv プロジェクト設定
├── models/
│   └── paraphrase-multilingual-MiniLM-L12-v2-mlx/  # MLX変換済みembeddingモデル
├── scripts/
│   ├── transcribe.py             # ASR処理（Parakeet MLX）
│   ├── transcribe.sh             # ASRシェルスクリプト
│   ├── segment.py                # 話題区切り検出（embedding類似度）
│   ├── segment-with-claude.py    # 話題区切り検出（Claude版・推奨）
│   ├── score.py                  # スコアリング（embedding版用）
│   ├── score-with-claude.py      # スコアリング（Claude版用・推奨）
│   ├── pipeline.py               # 統合パイプライン（embedding版）
│   ├── pipeline-claude.py        # 統合パイプライン（Claude版・推奨）
│   ├── shorts_generator.py       # 縦型動画生成（9:16）
│   └── hormozi_captions.py       # Hormozi風アニメ字幕
├── output/
│   ├── info-program.json         # ASR結果
│   ├── info-program-segments.json        # embedding版セグメント
│   ├── info-program-segments-claude.json # Claude版セグメント（推奨）
│   ├── info-program-scores.json          # embedding版スコア
│   ├── info-program-scores-claude.json   # Claude版スコア（推奨）
│   ├── clip-top1.mp4             # 切り出し動画サンプル
│   └── clip-top1-shorts.mp4      # ショート形式動画サンプル
└── docs/
    ├── architecture.md           # 設計ドキュメント
    └── handson.md                # この資料
```

---

## 処理フロー

### 推奨フロー（Claude版）

```
動画ファイル
    ↓
[1] ASR処理（transcribe.py）
    ↓
ASR結果JSON
    ↓
[2] 大セグメント検出（embedding類似度 閾値0.3）
    ↓
[3] 小セグメント検出（Claude Code）
    ↓
segments-claude.json
    ↓
[4] スコアリング（Claude Code）
    ↓
scores-claude.json
    ↓
[5] clips.json生成
    ↓
[6] 動画生成（オプション）
    ├── shorts_generator.py: 縦型9:16動画
    └── hormozi_captions.py: アニメ字幕追加
```

### 階層的セグメント検出の考え方

- **大セグメント**: embedding類似度で話題の大枠を検出（閾値0.3）
- **小セグメント**: 各大セグメント内でClaudeが15-90秒単位に分割
- **偽陰性を避ける方針**: 多めに候補を出し、スコアリングで選別

---

## 使用コマンド

### 環境セットアップ

```bash
cd /Users/washi/workspace/kirinuki
# 依存関係は uv.lock に記録済み
```

### Claude版フル実行（推奨）

```bash
# 1. ASR処理
uv run python scripts/transcribe.py video.mp4 -o output -c 180

# 2. 話題区切り検出（Claude版）
uv run python scripts/segment-with-claude.py output/video.json \
  --claude-model claude-opus-4-5-20251101

# 3. スコアリング（Claude版）
uv run python scripts/score-with-claude.py output/video-segments-claude.json
```

### embedding版フル実行

```bash
# 1. ASR処理
uv run python scripts/transcribe.py video.mp4 -o output -c 180

# 2. 話題区切り検出（階層的）
uv run python scripts/segment.py output/video.json -t 0.3 --small-threshold 0.6

# 3. スコアリング
uv run python scripts/score.py output/video-segments.json
```

### 統合パイプライン

```bash
# embedding版
uv run python scripts/pipeline.py video.mp4
uv run python scripts/pipeline.py video.mp4 --skip-asr  # ASRスキップ

# Claude版（推奨）
uv run python scripts/pipeline-claude.py video.mp4
```

### 動画生成

```bash
# 縦型ショート動画（9:16）を生成
uv run python scripts/shorts_generator.py \
  output/clip.mp4 \
  --asr output/clip.json \
  --title "動画タイトル" \
  --channel "チャンネル名"

# Hormozi風アニメ字幕を追加
uv run python scripts/hormozi_captions.py \
  output/clip.mp4 \
  output/clip.json \
  -o output/clip-hormozi.mp4
```

---

## 出力JSON構造

### segments-claude.json

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

### scores-claude.json

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

## 使用モデル

| 用途 | モデル | 場所 |
|------|--------|------|
| ASR | nvidia/parakeet-tdt_ctc-0.6b-ja | MLX版（HuggingFace） |
| 話題区切り（embedding） | paraphrase-multilingual-MiniLM-L12-v2 | MLX変換済み（ローカル） |
| 話題区切り・スコアリング | claude-opus-4-5-20251101 | Claude Code（サブスク） |

---

## 技術的注意事項

### メモリ管理

- **MLX**: `mx.clear_cache()` + `gc.collect()` をバッチ処理ごとに実行
- **Claude Code呼び出し**: `subprocess.Popen` + `start_new_session=True` でプロセスグループ作成、完了後 `os.killpg()` で確実にkill
- **ASR処理**: 180秒チャンクで分割処理

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

## 60分動画テスト結果（Claude版）

| 項目 | 値 |
|------|-----|
| 大セグメント | 18 |
| 小セグメント | 66 |
| スコア済み | 62 |
| 最高スコア | 7点 |
| 処理時間 | 約25分 |

### 上位候補

| 点 | 区間 | 話題 | 引き |
|----|------|------|------|
| 7 | 36:42-37:20 | 父の研究と挑戦 | 「できない」と言われ続けた父の |
| 6 | 07:40-08:12 | 仲間との交流不足 | ファイナリストに陰口言われてた |
| 6 | 30:22-30:45 | 社名とメッキ誤解 | 家業がメッキだと思ってたら… |
| 6 | 37:35-38:00 | 苦難と地域の支援 | 地域の町工場が支えてくれた |

---

## 次のステップ

### 優先度高

1. **閾値チューニング** - 大セグメント閾値の最適化
2. **プロンプト改善** - スコアリング精度向上

### 将来

3. **VLM拡張** - 画面変化検出（Molmo等）

### 完了済み（参考）

- ~~Claude版パイプライン統合~~ → `scripts/pipeline-claude.py`
- ~~clips.json生成~~ → パイプラインに統合
- ~~動画切り出し・生成~~ → `scripts/shorts_generator.py`, `scripts/hormozi_captions.py`
