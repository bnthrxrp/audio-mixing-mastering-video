#!/usr/bin/env python3
"""Normalize one audio stream to a new 24-bit WAV with two-pass FFmpeg loudnorm."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def execute(args):
    result = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"FFmpeg failed ({result.returncode}):\n{result.stderr[-4000:]}")
    return result.stderr


def stats(log):
    decoder = json.JSONDecoder()
    objects = []
    for i, c in enumerate(log):
        if c == '{':
            try:
                value, _ = decoder.raw_decode(log[i:])
                if isinstance(value, dict) and 'input_i' in value:
                    objects.append(value)
            except json.JSONDecodeError:
                pass
    if not objects:
        raise ValueError('loudnorm statistics missing; check filter availability')
    data = objects[-1]
    for key in ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset'):
        if not math.isfinite(float(data[key])):
            raise ValueError(f'{key} is not finite; input may be silent or too short')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path, help='new .wav output; never overwrites')
    parser.add_argument('--target-i', type=float, required=True)
    parser.add_argument('--target-tp', type=float, required=True)
    parser.add_argument('--target-lra', type=float, required=True)
    parser.add_argument('--sample-rate', type=int, default=48000)
    parser.add_argument('--audio-stream', type=int, default=0, help='zero-based audio stream index')
    parser.add_argument('--tolerance-lu', type=float, default=0.5)
    parser.add_argument('--tolerance-tp', type=float, default=0.3)
    parser.add_argument('--allow-dynamic', action='store_true')
    a = parser.parse_args()
    if not a.input.is_file() or a.output.suffix.lower() != '.wav' or a.output.exists():
        parser.error('input must exist; output must be a new .wav file')
    if not (-70 <= a.target_i <= -5 and -9 <= a.target_tp <= 0 and 1 <= a.target_lra <= 50):
        parser.error('targets outside loudnorm ranges (I −70..−5, TP −9..0, LRA 1..50)')
    if a.audio_stream < 0 or a.sample_rate <= 0 or a.tolerance_lu < 0 or a.tolerance_tp < 0:
        parser.error('invalid stream, sample rate or tolerance')
    params = f'I={a.target_i}:TP={a.target_tp}:LRA={a.target_lra}'
    common = ['ffmpeg', '-nostdin', '-hide_banner', '-i', str(a.input), '-map', f'0:a:{a.audio_stream}', '-vn']
    before = stats(execute(common + ['-af', f'loudnorm={params}:print_format=json', '-f', 'null', '-']))
    keys = {'measured_I': 'input_i', 'measured_TP': 'input_tp', 'measured_LRA': 'input_lra', 'measured_thresh': 'input_thresh', 'offset': 'target_offset'}
    measurements = ':'.join(f'{k}={float(before[v])}' for k, v in keys.items())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.loudnorm-', dir=a.output.parent) as d:
        tmp = Path(d) / 'render.wav'
        log = execute(common + ['-af', f'loudnorm={params}:{measurements}:linear=true:print_format=json', '-ar', str(a.sample_rate), '-c:a', 'pcm_s24le', '-n', str(tmp)])
        second = stats(log)
        mode = second.get('normalization_type', '').lower()
        if mode != 'linear' and not a.allow_dynamic:
            raise RuntimeError(f'normalization mode {mode!r} is not linear; output rejected; consider --allow-dynamic')
        after = stats(execute(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(tmp), '-map', '0:a:0', '-af', f'loudnorm={params}:print_format=json', '-f', 'null', '-']))
        if abs(float(after['input_i']) - a.target_i) > a.tolerance_lu or float(after['input_tp']) > a.target_tp + a.tolerance_tp:
            raise RuntimeError('output failed numeric QC: ' + json.dumps(after))
        # Hard link fails atomically if output already exists; temporary file is on same filesystem.
        os.link(tmp, a.output)
    print(json.dumps({'input': str(a.input), 'output': str(a.output), 'target_i': a.target_i, 'target_tp': a.target_tp, 'target_lra': a.target_lra, 'mode': mode, 'before': before, 'after': after, 'numeric_qc': 'pass', 'warning': 'PCM metrics only; no perceptual or codec compliance claim'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
