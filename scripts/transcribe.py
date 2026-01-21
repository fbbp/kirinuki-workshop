#!/usr/bin/env python3
"""
動画からASRでタイムスタンプ付きテキストを抽出
チャンクごとにメモリクリアを実行
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import mlx.core as mx


def extract_audio(video_path: Path, output_path: Path) -> None:
    """動画から音声を抽出"""
    print(f"=== 音声抽出中: {video_path} ===")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"音声抽出完了: {output_path}")


def transcribe_with_memory_clear(
    audio_path: Path,
    output_path: Path,
    model_id: str = "mlx-community/parakeet-tdt_ctc-0.6b-ja",
    chunk_duration: float = 180.0,
    overlap_duration: float = 15.0,
) -> dict:
    """メモリクリアしながらASR処理"""
    from parakeet_mlx import from_pretrained, DecodingConfig
    from parakeet_mlx.audio import load_audio

    print(f"=== モデルロード中: {model_id} ===")
    model = from_pretrained(model_id)
    print("モデルロード完了")

    print(f"=== ASR処理中 (chunk: {chunk_duration}s) ===")

    # コールバックで進捗表示とメモリクリア
    def chunk_callback(current_pos: int, total_pos: int):
        progress = current_pos / total_pos * 100
        print(f"  進捗: {progress:.1f}% ({current_pos}/{total_pos} samples)")
        # チャンク処理後にメモリクリア
        mx.clear_cache()

    result = model.transcribe(
        str(audio_path),
        chunk_duration=chunk_duration,
        overlap_duration=overlap_duration,
        chunk_callback=chunk_callback,
    )

    # 最終メモリクリア
    mx.clear_cache()

    # 結果を辞書に変換
    output_data = {
        "text": result.text,
        "sentences": [
            {
                "text": s.text,
                "start": s.start,
                "end": s.end,
                "duration": s.duration,
                "confidence": round(s.confidence, 3) if hasattr(s, 'confidence') else None,
                "tokens": [
                    {
                        "text": t.text,
                        "start": t.start,
                        "end": t.end,
                        "duration": t.duration,
                        "confidence": round(t.confidence, 3) if hasattr(t, 'confidence') else None,
                    }
                    for t in s.tokens
                ] if hasattr(s, 'tokens') else []
            }
            for s in result.sentences
        ]
    }

    # JSON出力
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"=== 完了 ===")
    print(f"出力: {output_path}")

    # モデル解放
    del model
    mx.clear_cache()

    return output_data


def main():
    parser = argparse.ArgumentParser(description="動画からASRでタイムスタンプ付きテキストを抽出")
    parser.add_argument("input", type=Path, help="入力動画ファイル")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("output"), help="出力ディレクトリ")
    parser.add_argument("-c", "--chunk-duration", type=float, default=180.0, help="チャンク長（秒）")
    parser.add_argument("--overlap", type=float, default=15.0, help="オーバーラップ長（秒）")
    parser.add_argument("--model", type=str, default="mlx-community/parakeet-tdt_ctc-0.6b-ja", help="モデルID")
    args = parser.parse_args()

    # 出力ディレクトリ作成
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # ファイル名
    basename = args.input.stem
    audio_path = args.output_dir / f"{basename}.wav"
    json_path = args.output_dir / f"{basename}.json"

    # 音声抽出
    extract_audio(args.input, audio_path)

    # ASR処理
    transcribe_with_memory_clear(
        audio_path,
        json_path,
        model_id=args.model,
        chunk_duration=args.chunk_duration,
        overlap_duration=args.overlap,
    )


if __name__ == "__main__":
    main()
