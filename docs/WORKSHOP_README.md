# AI駆動開発ワークショップ

YouTube長尺動画から縦型ショート動画を自動生成するパイプラインを、Claude Codeと一緒に構築するハンズオンワークショップです。

## 事前準備

### 1. GitHubアカウント

GitHubアカウントが必要です（無料でOK）。
https://github.com/

### 2. Groq APIキーを取得

1. https://console.groq.com/ にアクセス
2. アカウント作成（Google/GitHubログイン可）
3. 左メニュー「API Keys」→「Create API Key」
4. キーをコピーして安全な場所に保存

### 3. Anthropic APIキー（Claude Code用）

Claude Codeを使うにはAnthropicのAPIキーが必要です。

- **Claude Max/Proプランをお持ちの方**: Codespaces内で `claude login` を実行
- **APIキーをお持ちの方**: 環境変数に設定
- **お持ちでない方**: 当日、講師からゲストパスを案内します

---

## 当日の手順（GitHub Codespaces）

### 1. Codespacesを起動

1. https://github.com/fbbp/kirinuki-workshop にアクセス
2. 緑の `Code` ボタンをクリック
3. `Codespaces` タブを選択
4. `Create codespace on main` をクリック

環境構築に数分かかります。完了するとVS Codeがブラウザで開きます。

### 2. APIキーを設定

ターミナルで:

```bash
export GROQ_API_KEY="gsk_あなたのキー"
```

Claude Codeの認証:

```bash
# Max/Proプランの場合
claude login

# APIキーの場合
export ANTHROPIC_API_KEY="sk-ant-あなたのキー"
```

### 3. サンプル動画を配置

講師から提供されたURLからダウンロード:

```bash
mkdir -p ~/videos ~/output
curl -o ~/videos/sample.mp4 "講師から提供されたURL"
```

### 4. Claude Codeを起動

```bash
claude
```

### 5. 開発開始

Claude Codeに話しかけて開発を進めます:

```
> ~/videos/sample.mp4 から縦型ショート動画を作りたい。
> Groq APIを使ってまず文字起こしをしてほしい。
```

---

## トラブルシューティング

### Codespacesが起動しない

- ブラウザを更新してみる
- 別のブラウザで試す
- GitHubにログインしているか確認

### APIキーエラー

```bash
# 環境変数が設定されているか確認
echo $GROQ_API_KEY
echo $ANTHROPIC_API_KEY
```

### Claude Codeが動かない

```bash
# 再インストール
npm install -g @anthropic-ai/claude-code

# 認証確認
claude login
```

---

## ローカル環境で実行したい場合（オプション）

Codespacesではなくローカルで実行したい場合は、自分でDockerイメージをビルドできます。

### 前提条件

- Docker（OrbStack推奨）がインストール済み
- リポジトリをクローン済み

### ビルド & 実行

```bash
# リポジトリをクローン
git clone https://github.com/fbbp/kirinuki-workshop.git
cd kirinuki-workshop

# イメージをビルド
docker build -t kirinuki-workshop .

# コンテナを起動
docker run -it --rm \
  -e GROQ_API_KEY="gsk_あなたのキー" \
  -e ANTHROPIC_API_KEY="sk-ant-あなたのキー" \
  -v ~/workshop/videos:/videos:ro \
  -v ~/workshop/output:/output \
  kirinuki-workshop
```

---

## 参考リンク

- [Groq API ドキュメント](https://console.groq.com/docs)
- [Claude Code](https://docs.anthropic.com/claude-code)
- [GitHub Codespaces](https://docs.github.com/codespaces)

---

## サポート

ワークショップ中に困ったら、まず Claude Code に聞いてみてください:

```
> このエラーを解決して: [エラーメッセージをコピペ]
```

それでも解決しない場合は講師に声をかけてください。
