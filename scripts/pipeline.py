#!/usr/bin/env python3
"""
配信切り抜き自動化パイプライン
動画ファイルから1コマンドでショート候補リストを生成

Usage:
    uv run python scripts/pipeline.py video.mp4
    uv run python scripts/pipeline.py video.mp4 --skip-asr  # ASRスキップ
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_command(cmd: list[str], description: str, timeout: int = 600) -> bool:
    """コマンドを実行して結果を表示"""
    print(f"\n{'='*60}")
    print(f"[STEP] {description}")
    print(f"{'='*60}")
    print(f"  cmd: {' '.join(cmd[:5])}...")

    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            text=True
        )
        if result.returncode != 0:
            print(f"  [ERROR] Exit code: {result.returncode}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"  [ERROR] Timeout ({timeout}s)")
        return False
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def generate_clips_json(scores_path: Path, output_path: Path, min_score: int = 5) -> None:
    """スコア結果から最終的な切り抜きリストを生成"""
    with open(scores_path) as f:
        data = json.load(f)

    clips = []
    for r in data['results']:
        if r['score'] >= min_score:
            clips.append({
                'start': r['clip_start'],
                'end': r['clip_end'],
                'start_sec': r['clip_start_sec'],
                'end_sec': r['clip_end_sec'],
                'duration': r['clip_duration'],
                'score': r['score'],
                'topic': r['topic'],
                'hook': r['hook'],
                'reason': r['reason']
            })

    # スコア降順でソート
    clips.sort(key=lambda x: x['score'], reverse=True)

    output_data = {
        'generated_at': datetime.now().isoformat(),
        'source': data['source'],
        'min_score': min_score,
        'total_clips': len(clips),
        'clips': clips
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='配信切り抜き自動化パイプライン',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    # フル実行
    uv run python scripts/pipeline.py video.mp4

    # ASRスキップ（既存のASR結果を使用）
    uv run python scripts/pipeline.py video.mp4 --skip-asr

    # 閾値とスコア調整
    uv run python scripts/pipeline.py video.mp4 --threshold 0.4 --min-score 6
'''
    )
    parser.add_argument('video', help='入力動画ファイル')
    parser.add_argument('-o', '--output', default='output', help='出力ディレクトリ')
    parser.add_argument('--skip-asr', action='store_true', help='ASR処理をスキップ')
    parser.add_argument('--threshold', type=float, default=0.3,
                        help='話題区切りの類似度閾値 (default: 0.3)')
    parser.add_argument('--min-score', type=int, default=5,
                        help='最終出力の最小スコア (default: 5)')
    parser.add_argument('--model', default='sonnet',
                        help='スコアリングのClaudeモデル (default: sonnet)')
    parser.add_argument('--delay', type=float, default=2.0,
                        help='API呼び出し間の遅延秒 (default: 2.0)')
    args = parser.parse_args()

    video_path = Path(args.video)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = video_path.stem
    asr_json = output_dir / f"{stem}.json"
    segments_json = output_dir / f"{stem}-segments.json"
    scores_json = output_dir / f"{stem}-scores.json"
    clips_json = output_dir / f"{stem}-clips.json"

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           配信切り抜き自動化パイプライン                        ║
╚══════════════════════════════════════════════════════════════╝

入力: {video_path}
出力: {output_dir}/
""")

    # Step 1: ASR処理
    if args.skip_asr:
        print(f"[SKIP] ASR処理をスキップ（既存ファイル使用: {asr_json}）")
        if not asr_json.exists():
            print(f"  [ERROR] ASR結果が見つかりません: {asr_json}")
            sys.exit(1)
    else:
        cmd = [
            'uv', 'run', 'python', 'scripts/transcribe.py',
            str(video_path),
            '-o', str(output_dir),
            '-c', '180'
        ]
        if not run_command(cmd, "ASR処理（音声認識）", timeout=1800):
            sys.exit(1)

    # Step 2: 話題区切り検出
    cmd = [
        'uv', 'run', 'python', 'scripts/segment.py',
        str(asr_json),
        '-o', str(output_dir),
        '-t', str(args.threshold)
    ]
    if not run_command(cmd, "話題区切り検出", timeout=120):
        sys.exit(1)

    # Step 3: スコアリング
    cmd = [
        'uv', 'run', 'python', 'scripts/score.py',
        str(asr_json),
        '-s', str(segments_json),
        '-o', str(output_dir),
        '-m', args.model,
        '--delay', str(args.delay)
    ]
    if not run_command(cmd, "ショート適性スコアリング", timeout=600):
        sys.exit(1)

    # Step 4: 最終成果物生成
    print(f"\n{'='*60}")
    print(f"[STEP] 切り抜きリスト生成")
    print(f"{'='*60}")
    generate_clips_json(scores_json, clips_json, args.min_score)
    print(f"  保存: {clips_json}")

    # 結果表示
    with open(clips_json) as f:
        clips_data = json.load(f)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                         完了                                  ║
╚══════════════════════════════════════════════════════════════╝

生成ファイル:
  - {asr_json}
  - {segments_json}
  - {scores_json}
  - {clips_json}

切り抜き候補（スコア{args.min_score}以上）: {clips_data['total_clips']}件
""")

    if clips_data['clips']:
        print("推奨切り抜き区間:")
        for i, c in enumerate(clips_data['clips'][:5], 1):
            print(f"  {i}. [{c['score']}点] {c['start']}-{c['end']} ({c['duration']}s)")
            print(f"     {c['topic']}: {c['hook']}")


if __name__ == '__main__':
    main()
