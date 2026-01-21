#!/usr/bin/env python3
"""
Hormozi Captions スタイルの字幕を動画に焼き込む

特徴:
- 単語ごとにハイライト（色変化）
- 拡大・バウンドエフェクト
- 画面中央下部に配置
- MeCab形態素解析で単語境界を決定
"""

import argparse
import json
import math
from pathlib import Path

from moviepy import VideoFileClip, CompositeVideoClip, VideoClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import MeCab


def get_char_tokens(asr_path: str) -> list[dict]:
    """ASRデータから文字単位のトークンを取得"""
    with open(asr_path) as f:
        data = json.load(f)

    tokens = []
    for sent in data['sentences']:
        if 'tokens' not in sent:
            continue
        for tok in sent['tokens']:
            text = tok['text'].strip()
            if not text:
                continue
            tokens.append({
                'text': text,
                'start': tok['start'],
                'end': tok['end'],
            })
    return tokens


def expand_to_char_level(char_tokens: list[dict]) -> list[dict]:
    """
    複数文字トークンを1文字ずつに展開（タイムスタンプを線形補間）
    """
    result = []
    for tok in char_tokens:
        text = tok['text']
        if len(text) == 1:
            result.append(tok)
        else:
            # 複数文字の場合、均等に分割
            duration = tok['end'] - tok['start']
            char_duration = duration / len(text)
            for i, c in enumerate(text):
                result.append({
                    'text': c,
                    'start': tok['start'] + i * char_duration,
                    'end': tok['start'] + (i + 1) * char_duration,
                })
    return result


def merge_tokens_with_mecab(char_tokens: list[dict]) -> list[dict]:
    """
    MeCabで形態素解析し、文字トークンを単語単位にマージ
    """
    # まず1文字単位に展開
    single_chars = expand_to_char_level(char_tokens)

    # 全文を結合
    full_text = ''.join(t['text'] for t in single_chars)

    # MeCab解析
    mecab = MeCab.Tagger()
    node = mecab.parseToNode(full_text)

    words = []
    while node:
        surface = node.surface
        if surface:
            words.append(surface)
        node = node.next

    # 文字トークンを単語にマッピング
    word_tokens = []
    char_idx = 0

    for word in words:
        word_len = len(word)
        if char_idx + word_len > len(single_chars):
            break

        # 単語の文字数分のトークンを取得
        word_chars = single_chars[char_idx:char_idx + word_len]
        char_idx += word_len

        word_tokens.append({
            'text': word,
            'start': word_chars[0]['start'],
            'end': word_chars[-1]['end'],
        })

    return word_tokens


def filter_content_words(word_tokens: list[dict]) -> list[dict]:
    """助詞・助動詞などを前の単語にマージ"""
    mecab = MeCab.Tagger()
    result = []

    for tok in word_tokens:
        node = mecab.parseToNode(tok['text'])
        node = node.next  # BOS/EOSをスキップ

        if node and node.surface:
            features = node.feature.split(',')
            pos = features[0] if features else ''

            # 助詞・助動詞・記号は前の単語にマージ
            if pos in ['助詞', '助動詞', '記号'] and result:
                result[-1]['text'] += tok['text']
                result[-1]['end'] = tok['end']
            else:
                result.append(tok.copy())
        else:
            result.append(tok.copy())

    return result


def group_words(tokens: list[dict], max_words: int = 4) -> list[dict]:
    """単語をグループ化（表示単位）"""
    groups = []
    current = []

    for tok in tokens:
        current.append(tok)
        if len(current) >= max_words:
            groups.append({
                'tokens': current,
                'start': current[0]['start'],
                'end': current[-1]['end'],
            })
            current = []

    if current:
        groups.append({
            'tokens': current,
            'start': current[0]['start'],
            'end': current[-1]['end'],
        })

    return groups


def create_caption_frame(
    tokens: list[dict],
    current_time: float,
    width: int,
    height: int,
    font_size: int = 80,
) -> np.ndarray:
    """Hormoziスタイルのキャプションフレームを生成"""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # フォント設定
    try:
        font = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', font_size)
        font_large = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W9.ttc', int(font_size * 1.25))
    except:
        font = ImageFont.load_default()
        font_large = font

    # テキスト情報を収集
    texts = []
    total_width = 0
    spacing = 8

    for tok in tokens:
        is_current = tok['start'] <= current_time < tok['end']
        use_font = font_large if is_current else font

        bbox = draw.textbbox((0, 0), tok['text'], font=use_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        texts.append({
            'text': tok['text'],
            'width': text_width,
            'height': text_height,
            'font': use_font,
            'is_current': is_current,
            'start': tok['start'],
            'end': tok['end'],
        })
        total_width += text_width + spacing

    total_width -= spacing

    # 中央下部に配置
    x = (width - total_width) // 2
    y = int(height * 0.78)

    # 描画
    for t in texts:
        if t['is_current']:
            # バウンス効果
            progress = (current_time - t['start']) / max(0.01, t['end'] - t['start'])
            bounce = int(math.sin(progress * math.pi) * 8)
            scale_factor = 1.0 + 0.1 * math.sin(progress * math.pi)

            color = (255, 230, 0, 255)  # 黄色

            # アウトライン（太め）
            for ox in range(-4, 5, 2):
                for oy in range(-4, 5, 2):
                    if ox != 0 or oy != 0:
                        draw.text((x + ox, y + oy - bounce), t['text'],
                                  font=t['font'], fill=(0, 0, 0, 255))
            draw.text((x, y - bounce), t['text'], font=t['font'], fill=color)
        else:
            color = (255, 255, 255, 255)
            # アウトライン
            for ox in range(-3, 4, 2):
                for oy in range(-3, 4, 2):
                    if ox != 0 or oy != 0:
                        draw.text((x + ox, y + oy), t['text'],
                                  font=t['font'], fill=(0, 0, 0, 200))
            draw.text((x, y), t['text'], font=t['font'], fill=color)

        x += t['width'] + spacing

    return np.array(img)


def make_caption_clip(tokens: list[dict], start: float, end: float, size: tuple[int, int], font_size: int = 80):
    """キャプションクリップを生成"""
    width, height = size
    duration = end - start

    def make_frame(t):
        current_time = start + t
        return create_caption_frame(tokens, current_time, width, height, font_size)

    clip = VideoClip(make_frame, duration=duration)
    clip = clip.with_start(start)
    return clip


def add_hormozi_captions(
    video_path: str,
    asr_path: str,
    output_path: str,
    max_words: int = 4,
    font_size: int = 70,
):
    """動画にHormozi Captionsを追加"""
    print(f"[1/5] 動画を読み込み: {video_path}")
    video = VideoFileClip(video_path)
    size = video.size

    print(f"[2/5] 文字トークンを取得")
    char_tokens = get_char_tokens(asr_path)
    print(f"  文字トークン数: {len(char_tokens)}")

    print(f"[3/5] MeCabで単語にマージ")
    word_tokens = merge_tokens_with_mecab(char_tokens)
    word_tokens = filter_content_words(word_tokens)
    print(f"  単語トークン数: {len(word_tokens)}")

    print(f"[4/5] グループ化（{max_words}単語/グループ）")
    groups = group_words(word_tokens, max_words)
    print(f"  グループ数: {len(groups)}")

    # サンプル表示
    print("\n  [サンプル]")
    for g in groups[:3]:
        words = ' '.join(t['text'] for t in g['tokens'])
        print(f"    {g['start']:.2f}-{g['end']:.2f}: {words}")
    print()

    print(f"[5/5] キャプションを動画に合成")
    caption_clips = []
    for i, group in enumerate(groups):
        clip = make_caption_clip(
            group['tokens'],
            group['start'],
            group['end'],
            size,
            font_size=font_size,
        )
        caption_clips.append(clip)
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(groups)} グループ処理済み")

    final = CompositeVideoClip([video] + caption_clips)

    print(f"\n書き出し中: {output_path}")
    final.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        fps=video.fps,
        logger='bar',
    )

    video.close()
    final.close()
    print(f"完了: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Hormozi Captions を動画に追加')
    parser.add_argument('video', help='入力動画ファイル')
    parser.add_argument('--asr', required=True, help='ASR結果JSONファイル（文字起こし済み）')
    parser.add_argument('-o', '--output', help='出力動画ファイル')
    parser.add_argument('--words', type=int, default=4, help='1グループあたりの最大単語数 (default: 4)')
    parser.add_argument('--font-size', type=int, default=70, help='フォントサイズ (default: 70)')
    args = parser.parse_args()

    video_path = Path(args.video)
    output_path = args.output or str(video_path.with_stem(video_path.stem + '-hormozi'))

    add_hormozi_captions(
        str(video_path),
        args.asr,
        output_path,
        max_words=args.words,
        font_size=args.font_size,
    )


if __name__ == '__main__':
    main()
