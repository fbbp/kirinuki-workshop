#!/usr/bin/env python3
"""
話題区切り検出スクリプト（Claude版）
大セグメント: embedding類似度
小セグメント: Claude Codeで構造化分割
"""

import argparse
import gc
import json
import subprocess
import sys
import time
from pathlib import Path

import mlx.core as mx
import numpy as np


def load_model(model_path: str):
    """MLX embeddingモデルを読み込み"""
    from mlx_embeddings.utils import load
    return load(model_path)


def encode_texts(model, tokenizer, texts: list[str], batch_size: int = 4) -> np.ndarray:
    """テキストをembeddingに変換"""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        inputs = tokenizer._tokenizer(
            batch_texts, return_tensors='np', padding=True, truncation=True, max_length=128
        )
        input_ids = mx.array(inputs['input_ids'])
        attention_mask = mx.array(inputs['attention_mask'])
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        all_embeddings.append(np.array(outputs.text_embeds))
        del input_ids, attention_mask, outputs
        mx.clear_cache()
        gc.collect()
    return np.vstack(all_embeddings)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def detect_large_segments(embeddings: np.ndarray, sentences: list[dict], threshold: float = 0.3) -> list[dict]:
    """大セグメント検出（embedding類似度）"""
    boundaries = []
    for i in range(1, len(embeddings)):
        sim = cosine_similarity(embeddings[i - 1], embeddings[i])
        if sim < threshold:
            boundaries.append(i)

    boundary_indices = [0] + boundaries + [len(sentences)]
    large_segments = []

    for i in range(len(boundary_indices) - 1):
        start_idx = boundary_indices[i]
        end_idx = boundary_indices[i + 1]
        segment_sentences = sentences[start_idx:end_idx]
        if not segment_sentences:
            continue

        text = ''.join(s['text'] for s in segment_sentences)
        large_segments.append({
            'index': i,
            'start': segment_sentences[0]['start'],
            'end': segment_sentences[-1]['end'],
            'duration': segment_sentences[-1]['end'] - segment_sentences[0]['start'],
            'text': text.strip(),
            'sentence_indices': list(range(start_idx, end_idx))
        })

    return large_segments


def format_time(seconds: float) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"


def parse_time(time_str: str, base_seconds: float = 0) -> float:
    """MM:SS形式を秒に変換"""
    try:
        parts = time_str.replace(' ', '').split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return base_seconds
    except:
        return base_seconds


def split_with_claude(large_segment: dict, model: str = "sonnet") -> list[dict]:
    """
    Claude Codeで大セグメントを小セグメントに分割
    メモリ効率化: Popenで明示的にプロセス管理・kill
    """
    import os
    import signal

    seg_start = large_segment['start']
    seg_end = large_segment['end']
    text = large_segment['text'][:3000]

    prompt = f'''以下はYouTube動画の書き起こし（{format_time(seg_start)}〜{format_time(seg_end)}）です。

この中の話題の切り替わりを検出し、15〜90秒程度の小区間に分割してください。
話題が自然に完結する単位で区切ってください。

書き起こし:
---
{text}
---

以下のJSON形式のみで回答（説明不要）:
{{
  "segments": [
    {{"start": "MM:SS", "end": "MM:SS", "topic": "10字以内の話題"}},
    {{"start": "MM:SS", "end": "MM:SS", "topic": "10字以内の話題"}}
  ]
}}

注意:
- startとendは元動画の絶対時刻（{format_time(seg_start)}〜{format_time(seg_end)}の範囲内）
- 区間が重複・欠落しないように
- 分割不要なら1区間のみ返す'''

    cmd = [
        'claude', '-p', prompt,
        '--allowedTools', '[]',
        '--model', model,
        '--output-format', 'text'
    ]

    proc = None
    try:
        # 新しいプロセスグループで起動（子プロセスも一括kill可能に）
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True
        )

        try:
            stdout, stderr = proc.communicate(timeout=90)
        except subprocess.TimeoutExpired:
            # タイムアウト時はプロセスグループごとkill
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()
            return [{'start': seg_start, 'end': seg_end, 'topic': 'タイムアウト'}]

        if proc.returncode != 0:
            return [{'start': seg_start, 'end': seg_end, 'topic': '分割失敗'}]

        output = stdout.strip()
        start = output.find('{')
        end = output.rfind('}') + 1
        if start >= 0 and end > start:
            data = json.loads(output[start:end])
            segments = []
            for s in data.get('segments', []):
                segments.append({
                    'start': parse_time(s.get('start', ''), seg_start),
                    'end': parse_time(s.get('end', ''), seg_end),
                    'topic': s.get('topic', '')
                })
            return segments if segments else [{'start': seg_start, 'end': seg_end, 'topic': ''}]
        else:
            return [{'start': seg_start, 'end': seg_end, 'topic': 'パースエラー'}]

    except Exception as e:
        print(f"  [ERROR] {e}", file=sys.stderr)
        return [{'start': seg_start, 'end': seg_end, 'topic': 'エラー'}]
    finally:
        # 確実にプロセスを終了
        if proc is not None:
            try:
                if proc.poll() is None:  # まだ動いてたら
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait()
            except:
                pass
        gc.collect()


def main():
    parser = argparse.ArgumentParser(description='話題区切り検出（Claude版）')
    parser.add_argument('input', help='ASR結果JSONファイル')
    parser.add_argument('-o', '--output', default='output', help='出力ディレクトリ')
    parser.add_argument('-m', '--model-path',
                        default='./models/paraphrase-multilingual-MiniLM-L12-v2-mlx',
                        help='MLX embeddingモデルパス')
    parser.add_argument('-t', '--threshold', type=float, default=0.3,
                        help='大セグメント検出の類似度閾値 (default: 0.3)')
    parser.add_argument('--claude-model', default='sonnet',
                        help='小セグメント分割のClaudeモデル (default: sonnet)')
    parser.add_argument('--delay', type=float, default=2.0,
                        help='API呼び出し間の遅延（秒） (default: 2.0)')
    parser.add_argument('-b', '--batch-size', type=int, default=4)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ASR結果読み込み
    print(f"[1/5] ASR結果を読み込み: {input_path}")
    with open(input_path) as f:
        asr_data = json.load(f)
    sentences = asr_data['sentences']
    print(f"  ASRセグメント数: {len(sentences)}")

    # モデル読み込み
    print(f"[2/5] embeddingモデルを読み込み")
    model, tokenizer = load_model(args.model_path)

    # embedding生成
    print(f"[3/5] embedding生成中...")
    texts = [s['text'] for s in sentences]
    embeddings = encode_texts(model, tokenizer, texts, batch_size=args.batch_size)
    print(f"  Shape: {embeddings.shape}")

    del model, tokenizer
    mx.clear_cache()
    gc.collect()

    # 大セグメント検出
    print(f"[4/5] 大セグメント検出（閾値{args.threshold}）...")
    large_segments = detect_large_segments(embeddings, sentences, args.threshold)
    print(f"  大セグメント: {len(large_segments)}個")

    # Claude で小セグメント分割
    print(f"[5/5] Claudeで小セグメント分割中 (model={args.claude_model})...")
    all_small_segments = []

    for i, large_seg in enumerate(large_segments):
        time_str = f"{format_time(large_seg['start'])}-{format_time(large_seg['end'])}"
        print(f"  [{i+1}/{len(large_segments)}] {time_str} ({large_seg['duration']:.0f}s)...", end=' ', flush=True)

        if large_seg['duration'] < 30:
            # 短すぎる場合は分割せず
            small_segs = [{'start': large_seg['start'], 'end': large_seg['end'], 'topic': '短セグメント'}]
            print("skip (短い)")
        else:
            small_segs = split_with_claude(large_seg, model=args.claude_model)
            print(f"{len(small_segs)}分割")

        for j, ss in enumerate(small_segs):
            all_small_segments.append({
                'large_segment_index': i,
                'large_segment_start': large_seg['start'],
                'large_segment_end': large_seg['end'],
                'index': len(all_small_segments),
                'start': ss['start'],
                'end': ss['end'],
                'duration': ss['end'] - ss['start'],
                'topic': ss.get('topic', ''),
                'text': ''  # 後でマッピング可能
            })

        if i < len(large_segments) - 1 and large_seg['duration'] >= 30:
            time.sleep(args.delay)

    # 結果保存
    output_name = input_path.stem + '-segments-claude'
    segments_path = output_dir / f"{output_name}.json"

    result = {
        'source': str(input_path),
        'method': 'claude',
        'large_threshold': args.threshold,
        'claude_model': args.claude_model,
        'total_large_segments': len(large_segments),
        'total_small_segments': len(all_small_segments),
        'segments': all_small_segments
    }

    with open(segments_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n保存: {segments_path}")

    # サマリー
    print(f"\n[小セグメント一覧]")
    current_large = -1
    for seg in all_small_segments:
        if seg['large_segment_index'] != current_large:
            current_large = seg['large_segment_index']
            print(f"\n  === 大セグメント{current_large + 1} ===")
        print(f"    {format_time(seg['start'])}-{format_time(seg['end'])} ({seg['duration']:.0f}s) {seg['topic']}")


if __name__ == '__main__':
    main()
