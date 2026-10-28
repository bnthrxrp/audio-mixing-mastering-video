#!/usr/bin/env python3
"""Two-pass loudness normalization to a new WAV, with independent post-render QC."""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from audio_common import AudioError, digest, loudness, probe, run


def stats(log):
    decoder, objects = json.JSONDecoder(), []
    for i, char in enumerate(log):
        if char == '{':
            try:
                value, _ = decoder.raw_decode(log[i:])
                if isinstance(value, dict) and 'input_i' in value:
                    objects.append(value)
            except json.JSONDecodeError:
                pass
    if not objects:
        raise AudioError('loudnorm statistics unavailable')
    data = objects[-1]
    for key in ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset'):
        if not math.isfinite(float(data[key])):
            raise AudioError(f'{key} not finite; input may be silent or too short')
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path, help='new .wav output; never overwritten')
    p.add_argument('--target-i', type=float, required=True)
    p.add_argument('--target-tp', type=float, required=True)
    p.add_argument('--target-lra', type=float, required=True)
    p.add_argument('--sample-rate', type=int, default=48000)
    p.add_argument('--stream', '--audio-stream', dest='stream', type=int)
    p.add_argument('--dual-mono', action='store_true')
    p.add_argument('--tolerance-lu', type=float, default=0.5)
    p.add_argument('--allow-dynamic', action='store_true')
    p.add_argument('--timeout', type=int, default=600)
    p.add_argument('--max-seconds', type=int, default=7200)
    a = p.parse_args()
    if (not all(math.isfinite(x) for x in (a.target_i, a.target_tp, a.target_lra, a.tolerance_lu)) or
        not -70 <= a.target_i <= -5 or not -9 <= a.target_tp <= 0 or not 1 <= a.target_lra <= 50 or
        not 8000 <= a.sample_rate <= 192000 or a.tolerance_lu < 0 or a.timeout < 1 or a.max_seconds < 1):
        p.error('invalid or out-of-range target, tolerance, rate or timeout')
    if a.output.suffix.lower() != '.wav' or a.output.exists():
        p.error('output must be a new .wav file')
    source = probe(a.input, a.stream, max_seconds=a.max_seconds)
    if a.dual_mono and source['channels'] != 1:
        p.error('--dual-mono requires mono input')
    params = f'I={a.target_i}:TP={a.target_tp}:LRA={a.target_lra}:dual_mono={str(a.dual_mono).lower()}'
    common = ['ffmpeg', '-nostdin', '-hide_banner', '-protocol_whitelist', 'file,pipe',
              '-i', source['path'], '-map', f"0:a:{source['audio_index']}", '-vn']
    _, first_log = run(common + ['-af', f'loudnorm={params}:print_format=json', '-f', 'null', '-'], a.timeout)
    before = stats(first_log)
    keys = {'measured_I': 'input_i', 'measured_TP': 'input_tp', 'measured_LRA': 'input_lra',
            'measured_thresh': 'input_thresh', 'offset': 'target_offset'}
    measurements = ':'.join(f'{key}={float(before[value])}' for key, value in keys.items())
    destination = a.output.absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.loudnorm-', dir=destination.parent) as directory:
        tmp = Path(directory) / 'render.wav'
        _, second_log = run(common + ['-af', f'loudnorm={params}:{measurements}:linear=true:print_format=json',
                            '-ar', str(a.sample_rate), '-c:a', 'pcm_f32le', '-n', str(tmp)], a.timeout)
        second = stats(second_log)
        mode = second.get('normalization_type', '').lower()
        if mode != 'linear' and not a.allow_dynamic:
            raise AudioError(f'loudnorm used {mode!r}, not linear; candidate rejected (opt in with --allow-dynamic)')
        out = probe(tmp, 0, max_seconds=a.max_seconds)
        if out['channels'] != source['channels'] or abs(out['duration_s'] - source['duration_s']) > 0.05:
            raise AudioError('output channel count or duration does not match source')
        after = loudness(out, a.timeout, a.dual_mono)
        if (after['integrated_lufs'] is None or after['true_peak_dbtp'] is None or
            abs(after['integrated_lufs'] - a.target_i) > a.tolerance_lu or after['true_peak_dbtp'] > a.target_tp):
            raise AudioError('output failed independent loudness/true-peak QC: ' + json.dumps(after))
        output_hash = digest(tmp)
        os.link(tmp, destination)  # atomic, never replaces an existing path
    print(json.dumps({'schema_version': '1.0', 'input_sha256': digest(source['path']), 'output': str(destination),
          'output_sha256': output_hash, 'targets': {'lufs': a.target_i, 'true_peak_dbtp': a.target_tp,
          'lra_parameter_lu': a.target_lra, 'tolerance_lu': a.tolerance_lu}, 'mode': mode, 'before_loudnorm': before,
          'after_ebur128': after, 'numeric_qc': 'pass', 'warning': 'PCM only; perceptual and codec compliance not established'},
          ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except (AudioError, OSError, ValueError, KeyError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
