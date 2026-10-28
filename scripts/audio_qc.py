#!/usr/bin/env python3
"""Headless audio QC: objective measurements and explicitly labelled heuristics."""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import tempfile
from pathlib import Path
from audio_common import AudioError, db, digest, loudness, percentile, probe, run, same_timeline, scan, webrtc_frames


def number(frame):
    return frame['rms_dbfs'] if frame['rms_dbfs'] is not None else -200.0


def check(status, reason, confidence, **evidence):
    return {'status': status, 'reason': reason, 'confidence': confidence, 'evidence': evidence}


def make_report(a):
    info = probe(a.input, a.stream, max_seconds=a.max_seconds)
    raw = scan(info, a.timeout, a.max_seconds)
    met = loudness(info, a.timeout, a.dual_mono)
    silent = [f for f in raw['frames'] if number(f) <= a.silence_dbfs]
    silence_seconds = sum(f['end_s'] - f['start_s'] for f in silent)
    ratio = silence_seconds / raw['duration_s']
    clipped = max(raw['max_consecutive_near_full_scale']) >= a.clip_run
    checks = {
        'clipping': check('warning' if clipped else 'pass', 'near-full-scale consecutive samples are a clipping indicator, not proof',
                          'instrumental indicator', threshold_linear=0.999, minimum_run=a.clip_run,
                          near_full_scale_samples=raw['near_full_scale_samples'], max_run_per_channel=raw['max_consecutive_near_full_scale']),
        'distortion': check('indeterminate', 'clipping is only one possible cause; generic distortion cannot be proven without a reference or validated detector',
                            'insufficient evidence', clipping_indicator=clipped),
        'silence': check('warning' if ratio > a.max_silence_ratio else 'pass', 'low-energy windows, which may be intentional',
                         'instrumental indicator', threshold_dbfs=a.silence_dbfs, fraction=round(ratio, 4),
                         warning_fraction=a.max_silence_ratio, seconds=round(silence_seconds, 3)),
    }
    # EBU gates on silence/short material can produce sentinel values; do not treat them as valid measurements.
    usable = raw['duration_s'] >= 0.4 and len(silent) != len(raw['frames']) and met['true_peak_dbtp'] is not None
    for name, value, target, tolerance in (
        ('loudness', met['integrated_lufs'], a.target_i, a.tolerance_lu),
        ('true_peak', met['true_peak_dbtp'], a.target_tp, 0.0),
    ):
        if not usable or value is None:
            status, why = 'indeterminate', 'silence, short input or unavailable measurement'
        elif target is None:
            status, why = 'not_evaluated', 'no contractual target configured'
        else:
            ok = abs(value - target) <= tolerance if name == 'loudness' else value <= target
            status, why = ('pass' if ok else 'fail'), 'comparison with configured target'
        checks[name] = check(status, why, 'instrumental measurement', value=value, target=target, tolerance=tolerance)
    for name in ('noise', 'voice_level', 'music_masking', 'intelligibility'):
        checks[name] = check('indeterminate', 'requires aligned voice and/or music stems and a validated task profile', 'insufficient evidence')

    stems = {}
    if a.voice_stem:
        voice = probe(a.voice_stem, None, max_seconds=a.max_seconds)
        v = scan(voice, a.timeout, a.max_seconds)
        same_timeline(info, voice, raw, v)
        activity = webrtc_frames(voice, a.timeout, a.max_seconds) if a.vad == 'webrtc' else [number(f) > a.voice_gate_dbfs for f in v['frames']]
        length = min(len(activity), len(v['frames']))
        activity = activity[:length]
        voiced = [number(v['frames'][i]) for i in range(length) if activity[i]]
        quiet = [number(v['frames'][i]) for i in range(length) if not activity[i]]
        stems['voice'] = {'sha256': digest(voice['path']), 'stream': voice, 'vad': a.vad,
                          'speech_candidate_frames': len(voiced), 'non_speech_candidate_frames': len(quiet)}
        if len(voiced) >= 10:
            speech_median = statistics.median(voiced)
            checks['voice_level'] = check('warning' if speech_median < a.min_voice_dbfs else 'pass',
                'heuristic active-voice RMS relative to a configurable project threshold', 'low: VAD and content dependent',
                median_dbfs=round(speech_median, 2), minimum_dbfs=a.min_voice_dbfs, frames=len(voiced))
        if len(quiet) >= 10:
            floor = percentile(quiet, 0.5)
            checks['noise'] = check('warning' if floor > a.max_noise_dbfs else 'pass',
                'median level in non-speech candidate windows; ambience/music and VAD errors affect estimate',
                'low: non-speech level is not a noise classifier', median_dbfs=round(floor, 2),
                maximum_dbfs=a.max_noise_dbfs, frames=len(quiet))
        if a.music_stem:
            music = probe(a.music_stem, None, max_seconds=a.max_seconds)
            m = scan(music, a.timeout, a.max_seconds)
            same_timeline(voice, music, v, m)
            stems['music'] = {'sha256': digest(music['path']), 'stream': music}
            overlapping = [(number(v['frames'][i]), number(m['frames'][i]), v['frames'][i]['start_s'])
                           for i in range(min(length, len(m['frames']))) if activity[i] and number(m['frames'][i]) > -90]
            if len(overlapping) >= 10:
                margins = [x - y for x, y, _ in overlapping]
                risky = [(x, y, t) for x, y, t in overlapping if x - y < a.min_voice_music_margin_db]
                fraction = len(risky) / len(overlapping)
                checks['music_masking'] = check('warning' if fraction > a.max_masked_ratio else 'pass',
                    'broadband voice-to-music level is a screening proxy, not psychoacoustic masking',
                    'low: assumes synced isolated stems and valid VAD', median_margin_db=round(statistics.median(margins), 2),
                    minimum_margin_db=a.min_voice_music_margin_db, fraction_below_margin=round(fraction, 4),
                    warning_fraction=a.max_masked_ratio, example_starts_s=[round(t, 1) for _, _, t in risky[:12]])
                checks['intelligibility'] = check('indeterminate',
                    'voice/music margin alone cannot establish speech intelligibility; use validated speech tests or ASR WER with a reference',
                    'insufficient evidence', screening_margin_db=round(statistics.median(margins), 2))
    versions = {}
    for binary in ('ffmpeg', 'ffprobe'):
        out, _ = run([binary, '-version'], timeout=10)
        versions[binary] = out.decode('utf-8', 'replace').splitlines()[0]
    return {'schema_version': '1.0', 'input_sha256': digest(info['path']), 'stream': info,
            'tools': versions, 'measurements': {'decoded_duration_s': round(raw['duration_s'], 4),
            'sample_peak_dbfs': raw['sample_peak_dbfs'], 'loudness': met}, 'checks': checks,
            'stems': stems, 'assumptions': ['100 ms RMS windows', 'full program measured',
            'stem alignment is asserted by caller; matching timestamps do not prove content alignment',
            'automated checks do not certify perceptual or contractual quality'],
            'objective_gate': 'fail' if any(checks[x]['status'] == 'fail' for x in ('loudness', 'true_peak')) else
                              ('pass' if all(checks[x]['status'] == 'pass' for x in ('loudness', 'true_peak')) else 'indeterminate')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--stream', type=int, help='zero-based audio stream index; required for multiple tracks')
    p.add_argument('--voice-stem', type=Path)
    p.add_argument('--music-stem', type=Path)
    p.add_argument('--stems-synchronized', action='store_true', help='assert stems share content timeline and gain reference')
    p.add_argument('--vad', choices=['energy', 'webrtc'], default='energy')
    p.add_argument('--voice-gate-dbfs', type=float, default=-38)
    p.add_argument('--min-voice-dbfs', type=float, default=-30)
    p.add_argument('--max-noise-dbfs', type=float, default=-45)
    p.add_argument('--min-voice-music-margin-db', type=float, default=6)
    p.add_argument('--max-masked-ratio', type=float, default=0.3)
    p.add_argument('--silence-dbfs', type=float, default=-45)
    p.add_argument('--max-silence-ratio', type=float, default=0.3)
    p.add_argument('--clip-run', type=int, default=3)
    p.add_argument('--target-i', type=float)
    p.add_argument('--target-tp', type=float)
    p.add_argument('--dual-mono', action='store_true', help='measure mono intended for dual-mono playback')
    p.add_argument('--tolerance-lu', type=float, default=0.5)
    p.add_argument('--max-seconds', type=int, default=7200)
    p.add_argument('--timeout', type=int, default=600)
    p.add_argument('--report', type=Path, help='write JSON to a new file atomically')
    p.add_argument('--strict', action='store_true', help='exit 2 unless BOTH loudness targets pass')
    a = p.parse_args()
    if a.music_stem and not a.voice_stem:
        p.error('--music-stem requires --voice-stem')
    if (a.voice_stem or a.music_stem) and not a.stems_synchronized:
        p.error('stem analyses require --stems-synchronized')
    vals = [a.voice_gate_dbfs, a.min_voice_dbfs, a.max_noise_dbfs, a.min_voice_music_margin_db,
            a.max_masked_ratio, a.silence_dbfs, a.max_silence_ratio, a.tolerance_lu]
    vals += [x for x in (a.target_i, a.target_tp) if x is not None]
    if (not all(math.isfinite(x) for x in vals) or not 0 <= a.max_silence_ratio <= 1 or
        not 0 <= a.max_masked_ratio <= 1 or a.tolerance_lu < 0 or a.clip_run < 1 or
        a.max_seconds < 1 or a.timeout < 1):
        p.error('invalid or non-finite thresholds/limits')
    result = make_report(a)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if a.report:
        destination = a.report.absolute()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent, delete=False) as f:
            temporary = f.name
            try:
                f.write(encoded)
                f.flush()
                os.fsync(f.fileno())
            except BaseException:
                os.unlink(temporary)
                raise
        try:
            os.link(temporary, destination)
        finally:
            os.unlink(temporary)
    else:
        print(encoded, end='')
    return 2 if a.strict and result['objective_gate'] != 'pass' else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (AudioError, OSError, ValueError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
