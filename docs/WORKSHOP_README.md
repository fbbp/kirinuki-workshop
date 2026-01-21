# AI駆動開発ワークショップ

YouTube長尺動画から縦型ショート動画を自動生成するパイプラインを、Claude Codeと一緒に構築するハンズオンワークショップです。

## 事前準備

### 1. OrbStackをインストール

macOS用の軽量Dockerランタイムです。

```bash
# Homebrewでインストール
brew install orbstack

# または公式サイトからダウンロード
# https://orbstack.dev/
```

### 2. Groq APIキーを取得

1. https://console.groq.com/ にアクセス
2. アカウント作成（Google/GitHubログイン可）
3. 左メニュー「API Keys」→「Create API Key」
4. キーをコピーして安全な場所に保存

### 3. 作業ディレクトリを作成

```bash
mkdir -p ~/workshop/{videos,output}
```

---

## 当日の手順

### 1. サンプル動画を配置

講師から提供されたURLからダウンロードし、`~/workshop/videos/` に配置してください。

```bash
# 例
curl -o ~/workshop/videos/sample.mp4 "講師から提供されたURL"
```

### 2. コンテナを起動

```bash
docker run -it --rm \
  -e GROQ_API_KEY="gsk_あなたのキー" \
  -e ANTHROPIC_API_KEY="sk-ant-あなたのキー" \
  -v ~/workshop/videos:/videos:ro \
  -v ~/workshop/output:/output \
  ghcr.io/fbbp/kirinuki-workshop:latest
```

**オプション解説:**
- `-e GROQ_API_KEY` : Groq APIキーを設定
- `-e ANTHROPIC_API_KEY` : Claude Code用のAPIキー
- `-v ~/workshop/videos:/videos:ro` : 入力動画（読み取り専用）
- `-v ~/workshop/output:/output` : 出力先

### 3. Claude Codeを起動

コンテナ内で:

```bash
claude
```

### 4. 開発開始

Claude Codeに話しかけて開発を進めます:

```
> /videos/sample.mp4 から縦型ショート動画を作りたい。
> Groq APIを使ってまず文字起こしをしてほしい。
```

---

## docker-compose を使う場合

`docker-compose.yml` を使うとより簡単です。

### セットアップ

```bash
# .envファイルを作成
cat > ~/workshop/.env << 'EOF'
GROQ_API_KEY=gsk_あなたのキー
ANTHROPIC_API_KEY=sk-ant-あなたのキー
EOF
```

### 起動

```bash
cd ~/workshop
docker compose up -d
docker compose exec workshop bash

# コンテナ内で
claude
```

### 終了

```bash
docker compose down
```

---

## ファイル構成

```
~/workshop/
├── videos/           # 入力動画（読み取り専用）
│   └── sample.mp4
├── output/           # 生成された動画
│   └── short_001.mp4
├── .env              # APIキー（docker-compose用）
└── docker-compose.yml
```

---

## トラブルシューティング

### コンテナが起動しない

```bash
# OrbStackが起動しているか確認
orb status

# イメージを再取得
docker pull ghcr.io/fbbp/kirinuki-workshop:latest
```

### APIキーエラー

```bash
# 環境変数が設定されているか確認（コンテナ内で）
echo $GROQ_API_KEY
echo $ANTHROPIC_API_KEY
```

### 出力ファイルが見えない

ホストの `~/workshop/output/` を確認してください。
Finder または `ls ~/workshop/output/` で確認できます。

---

## 参考リンク

- [Groq API ドキュメント](https://console.groq.com/docs)
- [Claude Code](https://docs.anthropic.com/claude-code)
- [OrbStack](https://docs.orbstack.dev/)

---

## サポート

ワークショップ中に困ったら、まず Claude Code に聞いてみてください:

```
> このエラーを解決して: [エラーメッセージをコピペ]
```

それでも解決しない場合は講師に声をかけてください。
