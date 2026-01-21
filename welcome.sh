#!/bin/bash
# ウェルカムメッセージ

cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║       AI駆動開発ワークショップへようこそ!                    ║
╚══════════════════════════════════════════════════════════════╝

【ゴール】
  /videos/ の動画から縦型ショート動画を生成する

【ファイル構成】
  /videos/       → 入力動画（読み取り専用）
  /output/       → ここに出力
  ~/CLAUDE.md    → プロジェクト仕様書
  ~/reference.md → リファレンス資料

【始め方】
  1. claude と入力してClaude Codeを起動
  2. やりたいことを日本語で伝える

【例】
  > /videos/sample.mp4 から縦型ショートを作りたい

【困ったら】
  エラーメッセージをそのままClaude Codeに貼り付ける

EOF

# APIキーの確認
if [ -z "$GROQ_API_KEY" ]; then
    echo "⚠️  GROQ_API_KEY が設定されていません"
    echo "   export GROQ_API_KEY=\"gsk_xxxxx\" で設定してください"
    echo ""
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  ANTHROPIC_API_KEY が設定されていません"
    echo "   export ANTHROPIC_API_KEY=\"sk-ant-xxxxx\" で設定してください"
    echo ""
fi

# 入力動画の確認
if [ -d "/videos" ] && [ "$(ls -A /videos 2>/dev/null)" ]; then
    echo "📁 /videos/ 内のファイル:"
    ls -lh /videos/
    echo ""
else
    echo "⚠️  /videos/ に動画がありません"
    echo "   -v ~/workshop/videos:/videos:ro でマウントしてください"
    echo ""
fi

echo "準備ができたら claude を実行してください"
echo ""
