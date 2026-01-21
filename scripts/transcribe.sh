#!/bin/bash
# 動画からASRでタイムスタンプ付きテキストを抽出

set -e

INPUT_VIDEO="${1:-info-program.mp4}"
OUTPUT_DIR="${2:-output}"
CHUNK_DURATION="${3:-600}"  # デフォルト10分

# parakeet-mlx用のPython
PYTHON="$HOME/workspace/nemo-asr/experiments/.venv/bin/python"

# 出力ディレクトリ作成
mkdir -p "$OUTPUT_DIR"

# ファイル名取得（拡張子なし）
BASENAME=$(basename "$INPUT_VIDEO" | sed 's/\.[^.]*$//')

# 1. 動画から音声を抽出
echo "=== 音声抽出中: $INPUT_VIDEO ==="
ffmpeg -y -i "$INPUT_VIDEO" -vn -acodec pcm_s16le -ar 16000 -ac 1 "$OUTPUT_DIR/${BASENAME}.wav"

# 2. parakeet-mlxでASR処理
echo "=== ASR処理中 (chunk: ${CHUNK_DURATION}s) ==="
$PYTHON -m parakeet_mlx.cli "$OUTPUT_DIR/${BASENAME}.wav" \
    --model mlx-community/parakeet-tdt_ctc-0.6b-ja \
    --output-dir "$OUTPUT_DIR" \
    --output-format json \
    --chunk-duration "$CHUNK_DURATION" \
    --overlap-duration 15 \
    --verbose

echo "=== 完了 ==="
echo "出力: $OUTPUT_DIR/${BASENAME}.json"
