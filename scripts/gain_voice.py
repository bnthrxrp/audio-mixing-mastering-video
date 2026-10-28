#!/usr/bin/env python3
"""Apply bounded gain to an isolated voice stem and gate the float WAV candidate."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from audio_common import AudioError, digest, loudness, probe, run, scan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('voice', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--isolated-voice', action='store_true', help='assert input is a voice stem, not a full mix')
    p.add_argument('--gain-db', type=float, required=True)
    p.add_argument('--target-tp', type=float, required=True)
    p.add_argument('--timeout', type=int, default=600)
    p.add_argument('--max-seconds', type=int, default=7200)
    a = p.parse_args()
    if (not a.isolated_voice or not math.isfinite(a.gain_db) or not 0 < a.gain_db <= 6 or
        not math.isfinite(a.target_tp) or not -20 <= a.target_tp <= 0 or a.timeout < 1 or a.max_seconds < 1):
        p.error('require --isolated-voice, gain in (0,6] dB and true-peak target in [-20,0] dBTP')
    if a.output.suffix.lower() != '.wav' or a.output.exists():
        p.error('output must be a new .wav')
    src = probe(a.voice, None, max_seconds=a.max_seconds)
    before = scan(src, a.timeout, a.max_seconds)
    if sum(f['rms_dbfs'] is not None and f['rms_dbfs'] > -55 for f in before['frames']) < 10:
        raise AudioError('insufficient active signal for gain correction')
    dest = a.output.absolute()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.voice-gain-', dir=dest.parent) as directory:
        tmp = Path(directory) / 'candidate.wav'
        run(['ffmpeg', '-nostdin', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-i', src['path'],
             '-map', '0:a:0', '-af', f'volume={a.gain_db}dB', '-c:a', 'pcm_f32le', '-n', str(tmp)], a.timeout)
        out = probe(tmp, 0, max_seconds=a.max_seconds)
        after = scan(out, a.timeout, a.max_seconds)
        measured = loudness(out, a.timeout)
        peak = measured['true_peak_dbtp']
        if (out['sample_rate'] != src['sample_rate'] or out['channels'] != src['channels'] or
            abs(before['duration_s'] - after['duration_s']) > .05 or peak is None or peak > a.target_tp or
            any(v is not None and v > 0 for v in after['sample_peak_dbfs'])):
            raise AudioError('candidate failed duration/channel/rate/sample-peak or true-peak QC')
        output_hash = digest(tmp)
        os.link(tmp, dest)
    print(json.dumps({'schema_version': '1.0', 'action': 'voice_gain', 'input_sha256': digest(src['path']),
        'output_sha256': output_hash, 'output': str(dest), 'gain_db': a.gain_db, 'target_tp': a.target_tp,
        'after': measured, 'numeric_qc': 'pass',
        'warning': 'gain also raises background noise; this does not establish intelligibility'}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (AudioError, OSError, ValueError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
