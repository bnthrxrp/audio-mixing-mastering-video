#!/usr/bin/env python3
"""Local bounded parallel QC runner with content-addressed reports and JSONL events."""
import argparse
import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from audio_common import AudioError, digest, run

HERE = Path(__file__).resolve().parent
MEDIA = {'.wav', '.flac', '.mp3', '.mp4', '.m4a', '.mkv', '.mov', '.ogg', '.opus', '.aiff', '.aif'}


def atomically_create(path, content):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
        temp = f.name
        try:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            os.unlink(temp)
            raise
    try:
        os.link(temp, path)
    except FileExistsError:
        pass  # concurrent identical job wins; validate its content below
    finally:
        os.unlink(temp)


def worker(source, a, env_id):
    started, attempts = time.monotonic(), 0
    try:
        source_hash = digest(source)
        config = {'target_i': a.target_i, 'target_tp': a.target_tp, 'tolerance_lu': a.tolerance_lu,
                  'strict': a.strict, 'max_seconds': a.max_seconds, 'env': env_id}
        key = hashlib.sha256((source_hash + json.dumps(config, sort_keys=True, separators=(',', ':'))).encode()).hexdigest()
        report = a.output_dir / (key + '.json')
        if report.exists():
            data = json.loads(report.read_text(encoding='utf-8'))
            if data.get('input_sha256') != source_hash:
                return {'event': 'qc_complete', 'job_id': key, 'state': 'corrupt_cache', 'attempts': 0}
            return {'event': 'qc_complete', 'job_id': key, 'state': 'cached', 'gate': data['objective_gate'], 'attempts': 0}
        command = [sys.executable, str(HERE / 'audio_qc.py'), str(source), '--timeout', str(a.stage_timeout),
                   '--max-seconds', str(a.max_seconds), '--tolerance-lu', str(a.tolerance_lu)]
        if a.target_i is not None:
            command += ['--target-i', str(a.target_i)]
        if a.target_tp is not None:
            command += ['--target-tp', str(a.target_tp)]
        if a.strict:
            command += ['--strict']
        stdout, returncode = '', None
        for attempts in range(1, a.max_attempts + 1):
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       text=True, start_new_session=True)
            try:
                stdout, _ = process.communicate(timeout=a.job_timeout)
                returncode = process.returncode
                break  # only retry timeout; malformed media/configuration and QC failures are permanent
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                if attempts < a.max_attempts:
                    time.sleep(min(2 ** (attempts - 1), 5))
        if returncode not in (0, 2):
            return {'event': 'qc_complete', 'job_id': key, 'state': 'timeout' if returncode is None else 'error',
                    'attempts': attempts, 'duration_s': round(time.monotonic() - started, 3)}
        data = json.loads(stdout)
        if data.get('input_sha256') != source_hash or digest(source) != source_hash:
            return {'event': 'qc_complete', 'job_id': key, 'state': 'input_changed', 'attempts': attempts}
        atomically_create(report, stdout)
        existing = json.loads(report.read_text(encoding='utf-8'))
        if existing.get('input_sha256') != source_hash:
            return {'event': 'qc_complete', 'job_id': key, 'state': 'corrupt_cache', 'attempts': attempts}
        return {'event': 'qc_complete', 'job_id': key, 'state': 'complete', 'gate': existing['objective_gate'],
                'attempts': attempts, 'duration_s': round(time.monotonic() - started, 3)}
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return {'event': 'qc_complete', 'state': 'error', 'attempts': attempts}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input_dir', type=Path)
    p.add_argument('output_dir', type=Path)
    p.add_argument('--jobs', type=int, default=2)
    p.add_argument('--target-i', type=float)
    p.add_argument('--target-tp', type=float)
    p.add_argument('--tolerance-lu', type=float, default=0.5)
    p.add_argument('--strict', action='store_true')
    p.add_argument('--max-seconds', type=int, default=7200)
    p.add_argument('--stage-timeout', type=int, default=600)
    p.add_argument('--job-timeout', type=int, default=1800)
    p.add_argument('--max-attempts', type=int, default=2)
    a = p.parse_args()
    values = [a.tolerance_lu] + [x for x in (a.target_i, a.target_tp) if x is not None]
    if (not a.input_dir.is_dir() or not 1 <= a.jobs <= 32 or not 1 <= a.max_attempts <= 3 or
        min(a.max_seconds, a.stage_timeout, a.job_timeout) <= 0 or not all(math.isfinite(x) for x in values) or a.tolerance_lu < 0):
        p.error('invalid input directory, limits or targets')
    a.output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in a.input_dir.iterdir() if f.is_file() and f.suffix.lower() in MEDIA)
    if not files:
        p.error('no supported input files found')
    version, _ = run(['ffmpeg', '-version'], timeout=10)
    probe_version, _ = run(['ffprobe', '-version'], timeout=10)
    env_id = {'ffmpeg': version.decode('utf-8', 'replace').splitlines()[0], 'python': sys.version.split()[0],
              'ffprobe': probe_version.decode('utf-8', 'replace').splitlines()[0],
              'qc_sha256': digest(HERE / 'audio_qc.py'), 'common_sha256': digest(HERE / 'audio_common.py')}
    failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        for event in pool.map(lambda f: worker(f, a, env_id), files):
            print(json.dumps(event, ensure_ascii=False, allow_nan=False), flush=True)
            if event['state'] not in ('complete', 'cached') or (a.strict and event.get('gate') != 'pass'):
                failed += 1
    print(json.dumps({'event': 'batch_complete', 'total': len(files), 'failed': failed}), flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (AudioError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
