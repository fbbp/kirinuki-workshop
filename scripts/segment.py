#!/usr/bin/env python3
"""
話題区切り検出スクリプト（階層的分割対応）
大セグメント → 各区間内で小セグメント検出
"""

import argparse
import gc
import json
from pathlib import Path

import mlx.core as mx
import numpy as np


def load_model(model_path: str):
    """MLX embeddingモデルを読み込み"""
    from mlx_embeddings.utils import load
    return load(model_path)


def encode_texts(model, tokenizer, texts: list[str], batch_size: int = 4) -> np.ndarray:
    """
    テキストをバッチ処理でembeddingに変換
    メモリ管理のため小バッチで処理し、各バッチ後にキャッシュクリア
    """
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]

        inputs = tokenizer._tokenizer(
            batch_texts,
            return_tensors='np',
            padding=True,
            truncation=True,
            max_length=128
        )

        input_ids = mx.array(inputs['input_ids'])
        attention_mask = mx.array(inputs['attention_mask'])

        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        embeddings = outputs.text_embeds

        all_embeddings.append(np.array(embeddings))

        del input_ids, attention_mask, outputs, embeddings
        mx.clear_cache()
        gc.collect()

    return np.vstack(all_embeddings)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """コサイン類似度を計算"""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def detect_boundaries_in_range(
    embeddings: np.ndarray,
    start_idx: int,
    end_idx: int,
    threshold: float
) -> list[int]:
    """
    指定範囲内で境界を検出
    戻り値: 境界となるインデックスのリスト（絶対インデックス）
    """
    boundaries = []
    for i in range(start_idx + 1, end_idx):
        sim = cosine_similarity(embeddings[i - 1], embeddings[i])
        if sim < threshold:
            boundaries.append(i)
    return boundaries


def hierarchical_segmentation(
    embeddings: np.ndarray,
    sentences: list[dict],
    large_threshold: float = 0.3,
    small_threshold: float = 0.6
) -> list[dict]:
    """
    階層的セグメント検出
    1. 大セグメント検出（話題の大枠）
    2. 各大セグメント内で小セグメント検出
    """
    n = len(embeddings)

    # Step 1: 大セグメント境界検出
    large_boundaries = detect_boundaries_in_range(embeddings, 0, n, large_threshold)
    large_boundary_indices = [0] + large_boundaries + [n]

    print(f"  大セグメント: {len(large_boundary_indices) - 1}個（閾値{large_threshold}）")

    # Step 2: 各大セグメント内で小セグメント検出
    all_small_segments = []

    for i in range(len(large_boundary_indices) - 1):
        large_start = large_boundary_indices[i]
        large_end = large_boundary_indices[i + 1]

        # 大セグメント情報
        large_start_time = sentences[large_start]['start']
        large_end_time = sentences[large_end - 1]['end']

        # 大セグメント内で小セグメント検出
        small_boundaries = detect_boundaries_in_range(
            embeddings, large_start, large_end, small_threshold
        )
        small_boundary_indices = [large_start] + small_boundaries + [large_end]

        # 小セグメント生成
        for j in range(len(small_boundary_indices) - 1):
            small_start = small_boundary_indices[j]
            small_end = small_boundary_indices[j + 1]

            segment_sentences = sentences[small_start:small_end]
            if not segment_sentences:
                continue

            text = ''.join(s['text'] for s in segment_sentences)
            start_time = segment_sentences[0]['start']
            end_time = segment_sentences[-1]['end']

            all_small_segments.append({
                'large_segment_index': i,
                'large_segment_start': large_start_time,
                'large_segment_end': large_end_time,
                'index': len(all_small_segments),
                'start': start_time,
                'end': end_time,
                'duration': end_time - start_time,
                'text': text.strip(),
                'sentence_start_idx': small_start,
                'sentence_end_idx': small_end
            })

    print(f"  小セグメント: {len(all_small_segments)}個（閾値{small_threshold}）")

    return all_small_segments


def main():
    parser = argparse.ArgumentParser(description='話題区切り検出（階層的分割）')
    parser.add_argument('input', help='ASR結果JSONファイル')
    parser.add_argument('-o', '--output', default='output', help='出力ディレクトリ')
    parser.add_argument('-m', '--model',
                        default='./models/paraphrase-multilingual-MiniLM-L12-v2-mlx',
                        help='MLX embeddingモデルパス')
    parser.add_argument('-t', '--threshold', type=float, default=0.3,
                        help='大セグメント検出の類似度閾値 (default: 0.3)')
    parser.add_argument('--small-threshold', type=float, default=0.6,
                        help='小セグメント検出の類似度閾値 (default: 0.6)')
    parser.add_argument('-b', '--batch-size', type=int, default=4,
                        help='バッチサイズ (default: 4)')
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ASR結果読み込み
    print(f"[1/4] ASR結果を読み込み: {input_path}")
    with open(input_path) as f:
        asr_data = json.load(f)

    sentences = asr_data['sentences']
    print(f"  ASRセグメント数: {len(sentences)}")

    # モデル読み込み
    print(f"[2/4] モデルを読み込み: {args.model}")
    model, tokenizer = load_model(args.model)

    # embedding生成
    print(f"[3/4] embedding生成中...")
    texts = [s['text'] for s in sentences]
    embeddings = encode_texts(model, tokenizer, texts, batch_size=args.batch_size)
    print(f"  Shape: {embeddings.shape}")

    # モデル解放
    del model, tokenizer
    mx.clear_cache()
    gc.collect()

    # 階層的セグメント検出
    print(f"[4/4] 階層的セグメント検出中...")
    segments = hierarchical_segmentation(
        embeddings, sentences,
        large_threshold=args.threshold,
        small_threshold=args.small_threshold
    )

    # 結果保存
    output_name = input_path.stem + '-segments'
    segments_path = output_dir / f"{output_name}.json"

    result = {
        'source': str(input_path),
        'large_threshold': args.threshold,
        'small_threshold': args.small_threshold,
        'total_asr_segments': len(sentences),
        'total_small_segments': len(segments),
        'segments': segments
    }

    with open(segments_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n保存: {segments_path}")

    # サマリー表示
    print(f"\n[小セグメント一覧]")
    current_large = -1
    for seg in segments:
        if seg['large_segment_index'] != current_large:
            current_large = seg['large_segment_index']
            l_start = int(seg['large_segment_start'] // 60)
            l_end = int(seg['large_segment_end'] // 60)
            print(f"\n  === 大セグメント{current_large + 1} ({l_start}分〜{l_end}分) ===")

        start_m = int(seg['start'] // 60)
        start_s = int(seg['start'] % 60)
        end_m = int(seg['end'] // 60)
        end_s = int(seg['end'] % 60)
        print(f"    {start_m:02d}:{start_s:02d}-{end_m:02d}:{end_s:02d} ({seg['duration']:.0f}s)")


if __name__ == '__main__':
    main()
