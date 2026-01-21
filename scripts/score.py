#!/usr/bin/env python3
"""
ショート適性スコアリングスクリプト
小セグメントをclaude -pで評価し、15-60秒の最適切り抜き区間を提案
"""

import argparse
import gc
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def format_time(seconds: float) -> str:
    """秒をMM:SS形式に変換"""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"


def score_segment(segment: dict, model: str = "sonnet") -> dict:
    """
    claude -pでセグメントを評価し、15-60秒の最適切り抜き区間を提案
    Popenで明示的にプロセス管理・kill
    """
    seg_start = segment['start']
    seg_end = segment['end']

    prompt = f'''以下はYouTube動画の書き起こしです（{format_time(seg_start)}〜{format_time(seg_end)}）。

この中から **15〜60秒** のYouTubeショート向け切り抜き区間を提案してください。

評価基準:
- 話題の完結性（単独で理解できるか）
- エンタメ性・興味深さ・意外性
- 視聴者の関心を引く要素
- 冒頭で興味を引けるか

書き起こし:
---
{segment['text'][:2000]}
---

以下のJSON形式のみで回答（説明不要）:
{{
  "score": 1-10の整数,
  "clip_start": 推奨開始時刻（MM:SS形式、元動画の絶対時刻）,
  "clip_end": 推奨終了時刻（MM:SS形式、元動画の絶対時刻）,
  "topic": "15字以内の話題",
  "hook": "冒頭の引きとなるポイント（20字以内）",
  "reason": "30字以内の評価理由"
}}

切り抜き価値が低い場合はscore=1-3、clip_start/clip_endは最もマシな区間を指定。'''

    cmd = [
        'claude', '-p', prompt,
        '--allowedTools', '[]',
        '--model', model,
        '--output-format', 'text'
    ]

    proc = None
    try:
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
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()
            return {'score': 0, 'reason': 'Timeout'}

        if proc.returncode != 0:
            return {'score': 0, 'reason': 'API error'}

        output = stdout.strip()
        start = output.find('{')
        end = output.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(output[start:end])
        else:
            return {'score': 0, 'reason': 'Parse error'}

    except json.JSONDecodeError as e:
        print(f"  [ERROR] JSON parse: {e}", file=sys.stderr)
        return {'score': 0, 'reason': 'JSON error'}
    except Exception as e:
        print(f"  [ERROR] {e}", file=sys.stderr)
        return {'score': 0, 'reason': 'エラー'}
    finally:
        if proc is not None:
            try:
                if proc.poll() is None:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait()
            except:
                pass
        gc.collect()


def parse_time(time_str: str) -> float:
    """MM:SS形式を秒に変換"""
    try:
        parts = time_str.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return 0
    except:
        return 0


def main():
    parser = argparse.ArgumentParser(description='ショート適性スコアリング')
    parser.add_argument('segments_json', help='セグメント情報JSONファイル')
    parser.add_argument('-o', '--output', default='output', help='出力ディレクトリ')
    parser.add_argument('-m', '--model', default='sonnet', help='Claudeモデル (default: sonnet)')
    parser.add_argument('--min-duration', type=float, default=15,
                        help='最小セグメント長（秒）。これ未満はスキップ (default: 15)')
    parser.add_argument('--delay', type=float, default=2.0,
                        help='API呼び出し間の遅延（秒） (default: 2.0)')
    args = parser.parse_args()

    segments_path = Path(args.segments_json)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # セグメント情報読み込み
    print(f"[1/3] セグメント情報を読み込み: {segments_path}")
    with open(segments_path) as f:
        data = json.load(f)

    segments = data['segments']
    print(f"  小セグメント数: {len(segments)}")

    # 短すぎるセグメントをスキップ
    filtered = [s for s in segments if s['duration'] >= args.min_duration]
    print(f"  評価対象（{args.min_duration}秒以上）: {len(filtered)}")

    # スコアリング
    print(f"\n[2/3] スコアリング中 (model={args.model})...")
    results = []
    for i, seg in enumerate(filtered):
        time_str = f"{format_time(seg['start'])}-{format_time(seg['end'])}"
        print(f"  [{i+1}/{len(filtered)}] {time_str} ({seg['duration']:.0f}s)...", end=' ', flush=True)

        score_result = score_segment(seg, model=args.model)

        result = {
            'large_segment_index': seg.get('large_segment_index', 0),
            'segment_index': seg['index'],
            'segment_start': seg['start'],
            'segment_end': seg['end'],
            'segment_duration': seg['duration'],
            'score': score_result.get('score', 0),
            'clip_start': score_result.get('clip_start', ''),
            'clip_end': score_result.get('clip_end', ''),
            'clip_start_sec': parse_time(score_result.get('clip_start', '')),
            'clip_end_sec': parse_time(score_result.get('clip_end', '')),
            'topic': score_result.get('topic', ''),
            'hook': score_result.get('hook', ''),
            'reason': score_result.get('reason', '')
        }

        if result['clip_start_sec'] and result['clip_end_sec']:
            result['clip_duration'] = result['clip_end_sec'] - result['clip_start_sec']
        else:
            result['clip_duration'] = 0

        results.append(result)
        print(f"score={result['score']} | {result['clip_start']}-{result['clip_end']} | {result['topic']}")

        if i < len(filtered) - 1:
            time.sleep(args.delay)

    # スコア順にソート
    results.sort(key=lambda x: x['score'], reverse=True)

    # 結果保存
    print(f"\n[3/3] 結果保存中...")
    # segments_json が xxx-segments.json なら xxx-scores.json に
    stem = segments_path.stem.replace('-segments', '')
    output_path = output_dir / f"{stem}-scores.json"

    output_data = {
        'source': data['source'],
        'model': args.model,
        'large_threshold': data.get('large_threshold', 0),
        'small_threshold': data.get('small_threshold', 0),
        'total_segments': len(segments),
        'scored_segments': len(results),
        'results': results
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"  保存: {output_path}")

    # サマリー表示（全件）
    print(f"\n[スコア一覧（スコア降順）]")
    print(f"{'点':>3} | {'切り抜き区間':^13} | {'長さ':>4} | {'話題':<12} | {'引き':^15} | 理由")
    print("-" * 90)
    for r in results:
        clip_range = f"{r['clip_start']}-{r['clip_end']}"
        print(f"{r['score']:3d} | {clip_range:^13} | {r['clip_duration']:3.0f}s | {r['topic']:<12} | {r['hook']:<15} | {r['reason'][:25]}")


if __name__ == '__main__':
    main()
