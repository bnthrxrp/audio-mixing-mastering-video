#!/usr/bin/env python3
"""Apply bounded denoise to an isolated voice stem or duck an isolated music stem."""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile
from audio_common import AudioError, digest, probe, run, same_timeline, scan


def level(frame):
    return frame['rms_dbfs'] if frame['rms_dbfs'] is not None else -200.0


def median(values):
    return statistics.median(values) if values else None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    denoise = sub.add_parser('denoise', help='process one isolated voice stem')
    denoise.add_argument('voice', type=Path)
    denoise.add_argument('output', type=Path)
    denoise.add_argument('--noise-confirmed', action='store_true', help='policy/model asserts unwanted stationary noise in voice stem')
    denoise.add_argument('--noise-floor-dbfs', type=float, default=-40)
    denoise.add_argument('--reduction-db', type=float, default=6)
    duck = sub.add_parser('duck', help='reduce music only during the aligned voice stem')
    duck.add_argument('voice', type=Path)
    duck.add_argument('music', type=Path)
    duck.add_argument('output', type=Path, help='new ducked music stem (not a final mix)')
    duck.add_argument('--stems-synchronized', action='store_true')
    duck.add_argument('--sidechain-threshold', type=float, default=0.03)
    duck.add_argument('--ratio', type=float, default=2)
    for x in (denoise, duck):
        x.add_argument('--voice-gate-dbfs', type=float, default=-38)
        x.add_argument('--timeout', type=int, default=600)
        x.add_argument('--max-seconds', type=int, default=7200)
    a = p.parse_args()
    if not math.isfinite(a.voice_gate_dbfs) or a.timeout < 1 or a.max_seconds < 1:
        p.error('invalid timeout or gate')
    if a.action == 'denoise' and (not a.noise_confirmed or not math.isfinite(a.noise_floor_dbfs)
        or not math.isfinite(a.reduction_db) or not -80 <= a.noise_floor_dbfs <= -20
        or not 0.01 <= a.reduction_db <= 12):
        p.error('denoise requires --noise-confirmed and bounded noise-floor/reduction values')
    if a.action == 'duck' and (not a.stems_synchronized or not math.isfinite(a.sidechain_threshold)
        or not math.isfinite(a.ratio) or not 0.001 <= a.sidechain_threshold <= 1 or not 1 < a.ratio <= 4):
        p.error('duck requires --stems-synchronized and bounded sidechain settings')
    if a.output.suffix.lower() != '.wav' or a.output.exists():
        p.error('output must be a new .wav')
    voice = probe(a.voice, None, max_seconds=a.max_seconds)
    if abs(voice['start_s']) > 0.001:
        raise AudioError('voice stem must start at zero; align/export the stems before processing')
    v = scan(voice, a.timeout, a.max_seconds)
    activity = [level(frame) > a.voice_gate_dbfs for frame in v['frames']]
    if sum(activity) < 10:
        raise AudioError('insufficient active voice candidates (minimum one second)')
    dest = a.output.absolute()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.correction-', dir=dest.parent) as directory:
        tmp = Path(directory) / 'render.wav'
        common = ['ffmpeg', '-nostdin', '-v', 'error', '-protocol_whitelist', 'file,pipe']
        if a.action == 'denoise':
            if len(activity) - sum(activity) < 10:
                raise AudioError('insufficient non-voice candidate windows to validate noise reduction')
            cmd = common + ['-i', voice['path'], '-map', '0:a:0', '-vn', '-af',
                f'afftdn=nr={a.reduction_db}:nf={a.noise_floor_dbfs}', '-c:a', 'pcm_f32le', '-n', str(tmp)]
            source, before = voice, v
        else:
            music = probe(a.music, None, max_seconds=a.max_seconds)
            if abs(music['start_s']) > 0.001:
                raise AudioError('music stem must start at zero; align/export the stems before processing')
            m = scan(music, a.timeout, a.max_seconds)
            same_timeline(voice, music, v, m)
            # Some FFmpeg versions forward EOF while a sidechain FIFO still has audio.
            # Pad both inputs before the filter, then trim to the original music sample count.
            graph = (f'[0:a:0]apad=pad_dur=1[main];[1:a:0]apad=pad_dur=1[side];'
                     f'[main][side]sidechaincompress=threshold={a.sidechain_threshold}:ratio={a.ratio}:'
                     f'attack=20:release=250,atrim=end_sample={m["samples_per_channel"]}[duck]')
            cmd = common + ['-i', music['path'], '-protocol_whitelist', 'file,pipe', '-i', voice['path'],
                '-filter_complex', graph,
                '-map', '[duck]', '-c:a', 'pcm_f32le', '-n', str(tmp)]
            source, before = music, m
        run(cmd, a.timeout)
        after_meta = probe(tmp, 0, max_seconds=a.max_seconds)
        after = scan(after_meta, a.timeout, a.max_seconds)
        if (after_meta['channels'] != source['channels'] or after_meta['sample_rate'] != source['sample_rate'] or
            abs(after['duration_s'] - before['duration_s']) > 0.001):
            raise AudioError('candidate properties changed: '
                f"channels {source['channels']}→{after_meta['channels']}, "
                f"rate {source['sample_rate']}→{after_meta['sample_rate']}, "
                f"duration {before['duration_s']:.3f}→{after['duration_s']:.3f}s")
        n = min(len(activity), len(before['frames']), len(after['frames']))
        changes = [level(after['frames'][i]) - level(before['frames'][i]) for i in range(n)]
        voiced = [changes[i] for i in range(n) if activity[i] and level(before['frames'][i]) > -90]
        quiet = [changes[i] for i in range(n) if not activity[i] and level(before['frames'][i]) > -90]
        if len(voiced) < 10:
            raise AudioError('insufficient overlapping non-silent windows for correction QC')
        active_change, quiet_change = median(voiced), median(quiet)
        if a.action == 'denoise':
            if len(quiet) < 10 or quiet_change > -1.0 or not -1.5 <= active_change <= 1.0:
                raise AudioError('denoise rejected: need >=1 dB non-voice improvement and <=1.5 dB active median loss')
        else:
            if not -10 <= active_change <= -0.5 or (quiet_change is not None and quiet_change < -2.0):
                raise AudioError('duck rejected: insufficient or excessive attenuation during speech, or excessive change in pauses')
        old_peak = max(x for x in before['sample_peak_dbfs'] if x is not None) if any(x is not None for x in before['sample_peak_dbfs']) else -200
        new_peak = max(x for x in after['sample_peak_dbfs'] if x is not None) if any(x is not None for x in after['sample_peak_dbfs']) else -200
        if new_peak > old_peak + 0.3:
            raise AudioError('candidate sample peak increased by more than 0.3 dB')
        output_hash = digest(tmp)
        os.link(tmp, dest)
    report = {'schema_version': '1.0', 'action': a.action, 'voice_sha256': digest(voice['path']),
              'source_sha256': digest(source['path']), 'output': str(dest), 'output_sha256': output_hash,
              'qc': {'active_median_change_db': round(active_change, 2),
                     'nonvoice_median_change_db': round(quiet_change, 2) if quiet_change is not None else None,
                     'duration_preserved': True, 'channel_count_preserved': True},
              'warning': 'energy-based screening only; no guarantee of speech fidelity, perceptual quality or final-mix compliance'}
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except (AudioError, OSError, ValueError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
