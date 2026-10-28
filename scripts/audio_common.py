#!/usr/bin/env python3
"""Bounded local media utilities for the audio skill (Python standard library)."""
from __future__ import annotations

import array
import hashlib
import json
import math
import os
import re
import select
import subprocess
import sys
import tempfile
import time
from pathlib import Path


class AudioError(Exception):
    pass


def run(args, timeout=600):
    try:
        p = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AudioError(f'{args[0]} exceeded {timeout}s') from exc
    except OSError as exc:
        raise AudioError(f'cannot start {args[0]}: {exc}') from exc
    if p.returncode:
        raise AudioError(f'{args[0]} failed ({p.returncode}): ' + p.stderr.decode('utf-8', 'replace')[-3000:])
    return p.stdout, p.stderr.decode('utf-8', 'replace')


def local_file(path):
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file():
        raise AudioError('input must be a local regular file')
    return p


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def probe(path, index=None, timeout=30, max_seconds=7200, max_channels=8, max_rate=192000):
    path = local_file(path)
    out, _ = run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                  '-show_streams', '-show_format', '-of', 'json', str(path)], timeout)
    try:
        data = json.loads(out)
        streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']
        if not streams:
            raise AudioError('input contains no audio stream')
        if index is None:
            if len(streams) != 1:
                raise AudioError('multiple audio streams: select one explicitly with --stream')
            index = 0
        if index < 0 or index >= len(streams):
            raise AudioError('audio stream index does not exist')
        s = streams[index]
        rate, channels = int(s['sample_rate']), int(s['channels'])
        raw_duration = s.get('duration') or data.get('format', {}).get('duration')
        duration = float(raw_duration)
        if not math.isfinite(duration) or not 0 < duration <= max_seconds:
            raise AudioError('duration missing, invalid or over configured limit')
        if not 1 <= channels <= max_channels or not 8000 <= rate <= max_rate:
            raise AudioError('channel count or sample rate outside supported limits')
        start = float(s.get('start_time') or 0)
        if not math.isfinite(start):
            raise AudioError('invalid stream start time')
        return {'path': str(path), 'audio_index': index, 'stream_index': s['index'],
                'audio_streams': len(streams), 'sample_rate': rate, 'channels': channels,
                'channel_layout': s.get('channel_layout', 'unknown'), 'duration_s': duration,
                'start_s': start, 'codec': s.get('codec_name', 'unknown')}
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise AudioError(f'invalid or incomplete media metadata: {exc}') from exc


def pcm_chunks(meta, frame_bytes, timeout=600, max_seconds=7200, rate=None, channels=None, fmt='f32le'):
    cmd = ['ffmpeg', '-nostdin', '-v', 'error', '-protocol_whitelist', 'file,pipe',
           '-i', meta['path'], '-map', f"0:a:{meta['audio_index']}", '-vn']
    if rate:
        cmd += ['-ar', str(rate)]
    if channels:
        cmd += ['-ac', str(channels)]
    cmd += ['-f', fmt, '-acodec', 'pcm_s16le' if fmt == 's16le' else 'pcm_f32le', 'pipe:1']
    bytes_per_sample = 2 if fmt == 's16le' else 4
    limit = int(max_seconds * (rate or meta['sample_rate']) * (channels or meta['channels']) * bytes_per_sample)
    deadline, seen, buf = time.monotonic() + timeout, 0, bytearray()
    with tempfile.TemporaryFile() as err:
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err)
        except OSError as exc:
            raise AudioError(f'cannot start ffmpeg: {exc}') from exc
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AudioError('ffmpeg decode timed out')
                ready, _, _ = select.select([p.stdout], [], [], min(remaining, 1))
                if not ready:
                    continue
                block = os.read(p.stdout.fileno(), min(65536, max(frame_bytes, 4096)))
                if not block:
                    break
                seen += len(block)
                if seen > limit + frame_bytes:
                    raise AudioError('decoded audio exceeds duration limit')
                buf.extend(block)
                while len(buf) >= frame_bytes:
                    yield bytes(buf[:frame_bytes])
                    del buf[:frame_bytes]
            if buf:
                yield bytes(buf)
            try:
                rc = p.wait(timeout=max(0.01, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as exc:
                raise AudioError('ffmpeg decode timed out while exiting') from exc
            if rc:
                err.seek(0)
                raise AudioError(f'ffmpeg decode failed ({rc}): ' + err.read()[-3000:].decode('utf-8', 'replace'))
        finally:
            if p.poll() is None:
                p.kill()
            p.wait()
            p.stdout.close()


def db(value):
    return round(20 * math.log10(value), 3) if value > 0 else None


def percentile(values, q):
    if not values:
        return None
    seq = sorted(values)
    return seq[int((len(seq) - 1) * q)]


def scan(meta, timeout=600, max_seconds=7200, near=0.999):
    rate, channels = meta['sample_rate'], meta['channels']
    frame_samples = max(1, round(rate / 10))
    frames, peak, near_count, runs, max_runs = [], [0.] * channels, [0] * channels, [0] * channels, [0] * channels
    total = 0
    for block in pcm_chunks(meta, frame_samples * channels * 4, timeout, max_seconds):
        if len(block) % (4 * channels):
            raise AudioError('partial or corrupt decoded sample frame')
        samples = array.array('f')
        samples.frombytes(block)
        if sys.byteorder != 'little':
            samples.byteswap()
        sums = 0.0
        for i, value in enumerate(samples):
            if not math.isfinite(value):
                raise AudioError('non-finite sample encountered')
            c, level = i % channels, abs(value)
            peak[c] = max(peak[c], level)
            if level >= near:
                near_count[c] += 1
                runs[c] += 1
                max_runs[c] = max(max_runs[c], runs[c])
            else:
                runs[c] = 0
            sums += value * value
        count = len(samples) // channels
        if count:
            frames.append({'start_s': round(total / rate, 4), 'end_s': round((total + count) / rate, 4),
                           'rms_dbfs': db(math.sqrt(sums / len(samples)))})
            total += count
    if not total:
        raise AudioError('audio stream decoded to zero samples')
    return {'duration_s': total / rate, 'frames': frames, 'sample_peak_dbfs': [db(x) for x in peak],
            'near_full_scale_samples': near_count, 'max_consecutive_near_full_scale': max_runs,
            'samples_per_channel': total}


def webrtc_frames(meta, timeout=600, max_seconds=7200, aggressiveness=2):
    try:
        import webrtcvad
    except ImportError as exc:
        raise AudioError('WebRTC VAD unavailable: install a compatible webrtcvad package or use --vad energy') from exc
    vad, flags = webrtcvad.Vad(aggressiveness), []
    for block in pcm_chunks(meta, 640, timeout, max_seconds, rate=16000, channels=1, fmt='s16le'):
        if len(block) == 640:
            flags.append(bool(vad.is_speech(block, 16000)))
    return [sum(flags[i:i + 5]) >= 2 for i in range(0, len(flags), 5)]


def loudness(meta, timeout=600, dual_mono=False):
    _, log = run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'info',
                  '-protocol_whitelist', 'file,pipe', '-i', meta['path'], '-map',
                  f"0:a:{meta['audio_index']}", '-af', f'ebur128=peak=true:framelog=verbose:dualmono={int(dual_mono)}',
                  '-f', 'null', '-'], timeout)
    summary = log.rsplit('Summary:', 1)[-1]
    def extract(pattern):
        match = re.search(pattern, summary)
        if not match:
            raise AudioError('ebur128 summary unavailable; check FFmpeg filter support')
        v = float(match.group(1))
        return v if math.isfinite(v) else None
    number = r'([-+]?(?:\d+(?:\.\d+)?|inf))'
    return {'integrated_lufs': extract(r'(?m)^\s*I:\s*' + number),
            'lra_lu': extract(r'(?m)^\s*LRA:\s*' + number),
            'true_peak_dbtp': extract(r'(?m)^\s*Peak:\s*' + number),
            'method': 'FFmpeg ebur128 peak=true; program measurement'}


def same_timeline(a, b, decoded_a=None, decoded_b=None):
    tolerance = 0.05
    if abs(a['duration_s'] - b['duration_s']) > tolerance or abs(a['start_s'] - b['start_s']) > tolerance:
        raise AudioError('stems differ in duration or start timestamp by more than 50 ms')
    if decoded_a is not None and abs(decoded_a['duration_s'] - decoded_b['duration_s']) > tolerance:
        raise AudioError('decoded stem durations differ by more than 50 ms')
