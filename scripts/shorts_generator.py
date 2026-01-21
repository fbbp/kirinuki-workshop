#!/usr/bin/env python3
"""
YouTube Shorts 向け縦型動画生成

レイアウト（9:16 = 1080x1920）:
- 上部: チャンネル名
- 中央上: 概要テキスト
- 中央: 元動画（縦横比維持）
- 下部: Hormozi Captions
- 背景: 動画をぼかし+薄暗く
"""

import argparse
import json
import math
from pathlib import Path

from moviepy import (
    VideoFileClip,
    CompositeVideoClip,
    VideoClip,
    ColorClip,
)
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import MeCab


# ===== ASR/MeCab処理 =====

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
    """複数文字トークンを1文字ずつに展開"""
    result = []
    for tok in char_tokens:
        text = tok['text']
        if len(text) == 1:
            result.append(tok)
        else:
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
    """MeCabで形態素解析し、文字トークンを単語単位にマージ"""
    single_chars = expand_to_char_level(char_tokens)
    full_text = ''.join(t['text'] for t in single_chars)

    mecab = MeCab.Tagger()
    node = mecab.parseToNode(full_text)

    words = []
    while node:
        if node.surface:
            words.append(node.surface)
        node = node.next

    word_tokens = []
    char_idx = 0

    for word in words:
        word_len = len(word)
        if char_idx + word_len > len(single_chars):
            break
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
        node = node.next

        if node and node.surface:
            features = node.feature.split(',')
            pos = features[0] if features else ''
            if pos in ['助詞', '助動詞', '記号'] and result:
                result[-1]['text'] += tok['text']
                result[-1]['end'] = tok['end']
            else:
                result.append(tok.copy())
        else:
            result.append(tok.copy())

    return result


def group_words(tokens: list[dict], max_words: int = 5) -> list[dict]:
    """単語をグループ化"""
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


# ===== 描画関数 =====

def get_font(size: int, weight: str = 'W6'):
    """日本語フォントを取得"""
    try:
        return ImageFont.truetype(f'/System/Library/Fonts/ヒラギノ角ゴシック {weight}.ttc', size)
    except:
        return ImageFont.load_default()


def draw_text_with_outline(draw, pos, text, font, fill, outline_color=(0, 0, 0), outline_width=3):
    """アウトライン付きテキストを描画"""
    x, y = pos
    for ox in range(-outline_width, outline_width + 1):
        for oy in range(-outline_width, outline_width + 1):
            if ox != 0 or oy != 0:
                draw.text((x + ox, y + oy), text, font=font, fill=outline_color)
    draw.text((x, y), text, font=font, fill=fill)


def create_shorts_frame(
    video_frame: np.ndarray,
    current_time: float,
    word_groups: list[dict],
    channel_name: str,
    summary_text: str,
    output_size: tuple[int, int] = (1080, 1920),
) -> np.ndarray:
    """Shorts用フレームを生成"""
    width, height = output_size
    video_h, video_w = video_frame.shape[:2]

    # 背景: 動画をぼかし+薄暗く
    bg_img = Image.fromarray(video_frame)
    # リサイズして画面を埋める
    bg_scale = max(width / video_w, height / video_h)
    bg_new_w = int(video_w * bg_scale)
    bg_new_h = int(video_h * bg_scale)
    bg_img = bg_img.resize((bg_new_w, bg_new_h), Image.Resampling.LANCZOS)
    # 中央クロップ
    left = (bg_new_w - width) // 2
    top = (bg_new_h - height) // 2
    bg_img = bg_img.crop((left, top, left + width, top + height))
    # ぼかし
    bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=20))
    # 薄暗く
    bg_array = np.array(bg_img).astype(np.float32)
    bg_array = (bg_array * 0.3).astype(np.uint8)
    bg_img = Image.fromarray(bg_array)

    # メイン動画を中央に配置
    # 動画の縦横比を維持しつつ、幅80%に収める
    main_width = int(width * 0.85)
    scale = main_width / video_w
    main_height = int(video_h * scale)
    main_img = Image.fromarray(video_frame).resize((main_width, main_height), Image.Resampling.LANCZOS)

    # 動画の位置（やや上寄り）
    main_x = (width - main_width) // 2
    main_y = int(height * 0.28)

    bg_img.paste(main_img, (main_x, main_y))

    # 描画用
    draw = ImageDraw.Draw(bg_img)

    # 上部: チャンネル名（バッジスタイル）
    channel_font = get_font(36, 'W6')
    bbox = draw.textbbox((0, 0), channel_name, font=channel_font)
    ch_w = bbox[2] - bbox[0]
    ch_h = bbox[3] - bbox[1]
    ch_x = (width - ch_w) // 2
    ch_y = int(height * 0.08)

    # バッジ背景
    padding = 20
    badge_rect = [ch_x - padding, ch_y - padding // 2, ch_x + ch_w + padding, ch_y + ch_h + padding // 2]
    draw.rounded_rectangle(badge_rect, radius=10, fill=(60, 60, 60, 200))
    draw.text((ch_x, ch_y), channel_name, font=channel_font, fill=(255, 255, 255))

    # 中央上: 概要テキスト
    summary_font = get_font(52, 'W9')
    bbox = draw.textbbox((0, 0), summary_text, font=summary_font)
    sum_w = bbox[2] - bbox[0]
    sum_x = (width - sum_w) // 2
    sum_y = int(height * 0.18)
    draw_text_with_outline(draw, (sum_x, sum_y), summary_text, summary_font, (255, 230, 0), outline_width=4)

    # 下部: Hormozi Captions
    # 現在表示すべきグループを探す
    current_group = None
    for g in word_groups:
        if g['start'] <= current_time < g['end']:
            current_group = g
            break

    if current_group:
        tokens = current_group['tokens']
        caption_font = get_font(56, 'W6')
        caption_font_large = get_font(70, 'W9')

        # テキスト幅を計算
        texts = []
        total_width = 0
        spacing = 12

        for tok in tokens:
            is_current = tok['start'] <= current_time < tok['end']
            use_font = caption_font_large if is_current else caption_font
            bbox = draw.textbbox((0, 0), tok['text'], font=use_font)
            text_width = bbox[2] - bbox[0]
            texts.append({
                'text': tok['text'],
                'width': text_width,
                'font': use_font,
                'is_current': is_current,
                'start': tok['start'],
                'end': tok['end'],
            })
            total_width += text_width + spacing

        total_width -= spacing

        # 複数行に分割（幅が画面の90%を超える場合）
        max_line_width = int(width * 0.9)
        lines = []
        current_line = []
        current_line_width = 0

        for t in texts:
            if current_line_width + t['width'] + spacing > max_line_width and current_line:
                lines.append(current_line)
                current_line = [t]
                current_line_width = t['width']
            else:
                current_line.append(t)
                current_line_width += t['width'] + spacing

        if current_line:
            lines.append(current_line)

        # 描画位置
        caption_y_base = int(height * 0.78)
        line_height = 90

        for line_idx, line in enumerate(lines):
            line_width = sum(t['width'] for t in line) + spacing * (len(line) - 1)
            x = (width - line_width) // 2
            y = caption_y_base + line_idx * line_height

            for t in line:
                if t['is_current']:
                    progress = (current_time - t['start']) / max(0.01, t['end'] - t['start'])
                    bounce = int(math.sin(progress * math.pi) * 10)
                    color = (255, 230, 0)
                    draw_text_with_outline(draw, (x, y - bounce), t['text'], t['font'], color, outline_width=5)
                else:
                    draw_text_with_outline(draw, (x, y), t['text'], t['font'], (255, 255, 255), outline_width=4)
                x += t['width'] + spacing

    return np.array(bg_img)


def generate_shorts_video(
    video_path: str,
    asr_path: str,
    output_path: str,
    channel_name: str = "デフォルト切り抜きチャンネル",
    summary_text: str = "xxxxxxxx",
    max_words: int = 5,
    output_size: tuple[int, int] = (1080, 1920),
):
    """Shorts動画を生成"""
    print(f"[1/5] 動画を読み込み: {video_path}")
    video = VideoFileClip(video_path)
    duration = video.duration
    fps = video.fps

    print(f"[2/5] ASRトークンを処理")
    char_tokens = get_char_tokens(asr_path)
    word_tokens = merge_tokens_with_mecab(char_tokens)
    word_tokens = filter_content_words(word_tokens)
    print(f"  単語トークン数: {len(word_tokens)}")

    print(f"[3/5] グループ化（{max_words}単語/グループ）")
    word_groups = group_words(word_tokens, max_words)
    print(f"  グループ数: {len(word_groups)}")

    print(f"[4/5] Shorts動画を生成中...")

    def make_frame(t):
        # 元動画のフレームを取得
        video_frame = video.get_frame(t)
        return create_shorts_frame(
            video_frame, t, word_groups, channel_name, summary_text, output_size
        )

    shorts_clip = VideoClip(make_frame, duration=duration)
    shorts_clip = shorts_clip.with_audio(video.audio)

    print(f"[5/5] 書き出し中: {output_path}")
    shorts_clip.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        fps=fps,
        logger='bar',
    )

    video.close()
    shorts_clip.close()
    print(f"完了: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='YouTube Shorts 向け縦型動画生成')
    parser.add_argument('video', help='入力動画ファイル')
    parser.add_argument('--asr', required=True, help='ASR結果JSONファイル')
    parser.add_argument('-o', '--output', help='出力動画ファイル')
    parser.add_argument('--channel', default='デフォルト切り抜きチャンネル', help='チャンネル名')
    parser.add_argument('--summary', default='xxxxxxxx', help='概要テキスト')
    parser.add_argument('--words', type=int, default=5, help='1グループあたりの最大単語数 (default: 5)')
    parser.add_argument('--width', type=int, default=1080, help='出力幅 (default: 1080)')
    parser.add_argument('--height', type=int, default=1920, help='出力高さ (default: 1920)')
    args = parser.parse_args()

    video_path = Path(args.video)
    output_path = args.output or str(video_path.with_stem(video_path.stem + '-shorts'))

    generate_shorts_video(
        str(video_path),
        args.asr,
        output_path,
        channel_name=args.channel,
        summary_text=args.summary,
        max_words=args.words,
        output_size=(args.width, args.height),
    )


if __name__ == '__main__':
    main()
