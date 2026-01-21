# AI駆動開発ワークショップ - リファレンス資料

## 1. AI駆動開発とは

### Vibe Coding

「雰囲気でコードを書く」- AIに意図を伝え、実装はAIに任せる開発スタイル。

従来の開発:
```
要件 → 設計 → 実装（人間がコードを書く）→ テスト → デプロイ
```

AI駆動開発:
```
要件 → AIに説明 → AIが実装 → 人間がレビュー → 修正指示 → 完成
```

### 世代の違い

| 世代 | 特徴 | ツール例 |
|------|------|----------|
| 第1世代 | コード補完 | GitHub Copilot |
| 第2世代 | チャット型 | ChatGPT, Claude.ai |
| 第3世代 | エージェント型 | Claude Code, Cursor Agent |

第3世代では、AIが自律的にファイルを読み書きし、コマンドを実行する。

---

## 2. 仕様駆動開発

AIに「良い仕様」を伝えることが成功の鍵。

### 良い仕様の例

```
## ゴール
1時間の横型動画から、縦型ショート動画を生成する

## 入力
- MP4ファイル（1920x1080, 60分）

## 出力
- 縦型MP4（1080x1920, 15-60秒）
- 日本語字幕付き

## 制約
- Groq APIを使用（GROQ_API_KEY環境変数）
- 出力は /output/ に保存
```

### 悪い仕様の例

```
動画をショートにして
```

→ 具体性がないとAIは適切な判断ができない

---

## 3. Claude Codeの使い方

### 基本コマンド

```bash
# 起動
claude

# 会話開始
> 動画からショートを作るスクリプトを書いて

# 終了
> /exit
```

### 思考モード

| コマンド | 用途 |
|----------|------|
| `think` | 通常の思考（デフォルト） |
| `think hard` | より深い思考 |
| `ultrathink` | 最も深い思考（複雑な問題向け） |

```
> ultrathink この設計で問題ないか検証して
```

### CLAUDE.md

プロジェクトルートに `CLAUDE.md` を置くと、Claude Codeが自動で読み込む。
プロジェクトの文脈・制約・ゴールを記述しておく。

---

## 4. 今回のソリューション

### パイプライン概要

```
[入力] 1時間の横型動画
         ↓
    ┌────────────────┐
    │ Groq Whisper   │ ← 音声認識（$0.04/時間）
    │ ASR処理        │
    └────────────────┘
         ↓
    単語タイムスタンプ付きJSON
         ↓
    ┌────────────────┐
    │ Groq LLM       │ ← トピック分割・スコアリング
    │ gpt-oss-120b   │    （$0.15/M tokens）
    └────────────────┘
         ↓
    ショート向き区間リスト
         ↓
    ┌────────────────┐
    │ ffmpeg         │ ← 動画切り出し・変換
    │ moviepy        │
    └────────────────┘
         ↓
    ┌────────────────┐
    │ MeCab          │ ← 日本語字幕生成
    │ 形態素解析     │
    └────────────────┘
         ↓
[出力] 縦型ショート動画（字幕付き）
```

### Groq API

#### Whisper（音声認識）

```python
from groq import Groq

client = Groq()  # GROQ_API_KEYを自動で読み込み

with open("video.mp4", "rb") as f:
    result = client.audio.transcriptions.create(
        file=f,
        model="whisper-large-v3-turbo",
        response_format="verbose_json",
        timestamp_granularities=["word", "segment"],
        language="ja"
    )

# result.words → 単語ごとのタイムスタンプ
# result.segments → セグメントごとの文字起こし
```

#### LLM（テキスト処理）

```python
response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "あなたは動画編集のプロです"},
        {"role": "user", "content": "この文字起こしから、ショート向きの区間を特定してください"}
    ],
    temperature=0.3
)
```

### 動画処理

#### ffmpegで切り出し

```bash
# 30秒から60秒間を切り出し
ffmpeg -i input.mp4 -ss 30 -t 60 -c copy output.mp4
```

#### moviepyで縦型変換

```python
from moviepy.editor import VideoFileClip

clip = VideoFileClip("input.mp4")

# 中央をクロップして9:16に
w, h = clip.size
new_w = int(h * 9 / 16)
x1 = (w - new_w) // 2
cropped = clip.crop(x1=x1, x2=x1+new_w)

cropped.write_videofile("output.mp4")
```

### MeCab（日本語処理）

```python
import MeCab

tagger = MeCab.Tagger()
result = tagger.parse("今日は良い天気です")

# 今日    名詞,副詞可能,*,*,*,*,今日,キョウ,キョー
# は      助詞,係助詞,*,*,*,*,は,ハ,ワ
# ...
```

---

## 5. 用語集

| 用語 | 説明 |
|------|------|
| ASR | Automatic Speech Recognition（自動音声認識） |
| LLM | Large Language Model（大規模言語モデル） |
| Whisper | OpenAI開発の音声認識モデル |
| ffmpeg | 動画処理の定番ツール |
| moviepy | Pythonの動画編集ライブラリ |
| MeCab | 日本語形態素解析エンジン |
| uv | 高速なPythonパッケージマネージャ |

---

## 6. 環境構築手順

### 事前準備

1. **OrbStack** インストール
   - https://orbstack.dev/ からダウンロード
   - Docker Desktop より軽量・高速

2. **Groq APIキー** 取得
   - https://console.groq.com/ でアカウント作成
   - API Keysページでキー生成

### ワークショップ当日

```bash
# 1. 作業ディレクトリ作成
mkdir -p ~/workshop/{videos,output}

# 2. サンプル動画を配置
# （講師から提供されたURLからダウンロード）

# 3. コンテナ起動
docker run -it --rm \
  -e GROQ_API_KEY="gsk_xxxxx" \
  -v ~/workshop/videos:/videos:ro \
  -v ~/workshop/output:/output \
  ghcr.io/fbbp/kirinuki-workshop:latest

# 4. Claude Code起動
claude
```

---

## 7. トラブルシューティング

### よくある問題

#### Groq APIエラー

```
Error: Invalid API key
```
→ `GROQ_API_KEY` が正しく設定されているか確認

```bash
echo $GROQ_API_KEY
```

#### ffmpegエラー

```
Unknown encoder 'libx264'
```
→ コンテナ内のffmpegにはコーデックが含まれている。ホストのffmpegを使っていないか確認。

#### MeCabエラー

```
error in MeCab::Tagger::parse()
```
→ 辞書が見つからない。`unidic-lite` がインストールされているか確認。

```bash
uv add unidic-lite
```

### 困ったら

1. **エラーメッセージをそのままClaude Codeに貼る**
   ```
   > このエラーを解決して: [エラーメッセージ]
   ```

2. **現状を説明する**
   ```
   > 動画の切り出しまではできたけど、字幕の追加で詰まっている
   ```

3. **ゴールを再確認する**
   ```
   > 改めてゴールを確認: 縦型ショート動画を作りたい。今どこまでできてる？
   ```

---

## 8. 心構え

### 完成しなくてもOK

このワークショップのゴールは「完成させること」ではなく「**自分で続けられる自信を得ること**」。

- 詰まったらAIに聞く
- エラーが出たらAIに見せる
- わからなかったらAIに説明してもらう

この習慣を身につければ、ワークショップ後も一人で開発を続けられる。

### AIとの対話のコツ

1. **具体的に伝える** - 「動画を処理して」より「30秒から60秒を切り出して」
2. **段階的に進める** - 一度に全部やろうとしない
3. **エラーは宝** - エラーメッセージはAIへの最高の入力

### 今日のゴール

```
入力: サンプル動画（3-5分）
出力: 縦型ショート動画（1本でも作れたら成功）
```

時間内に完成しなくても、「あとは家で続けられる」状態になればOK。
