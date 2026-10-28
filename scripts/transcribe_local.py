#!/usr/bin/env python3
"""Offline Faster-Whisper transcription with local model, bounded runtime and atomic output."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
from audio_common import AudioError, digest, probe, run


def model_hash(model):
    required = ['model.bin', 'config.json', 'tokenizer.json']
    if not model.is_dir() or any(not (model / name).is_file() for name in required):
        raise AudioError('model directory must contain model.bin, config.json and tokenizer.json')
    h = hashlib.sha256()
    files = sorted(f for f in model.rglob('*') if f.is_file())
    for f in files:
        name = f.relative_to(model).as_posix().encode()
        h.update(len(name).to_bytes(4, 'big'))
        h.update(name)
        h.update(bytes.fromhex(digest(f)))
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path, help='new UTF-8 JSON transcript; treat as sensitive')
    p.add_argument('--model', type=Path, required=True, help='local converted Faster-Whisper model directory')
    p.add_argument('--stream', type=int)
    p.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    p.add_argument('--compute-type', choices=['int8', 'float16', 'float32'], default='int8')
    p.add_argument('--language', default='pt')
    p.add_argument('--vad-filter', action='store_true')
    p.add_argument('--timeout', type=int, default=1800)
    p.add_argument('--max-seconds', type=int, default=7200)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    a = p.parse_args()
    if not re.fullmatch(r'[a-z]{2,3}', a.language) or a.timeout < 1 or a.max_seconds < 1:
        p.error('invalid language or time limits')
    if a.output.suffix.lower() != '.json' or a.output.exists():
        p.error('output must be a new .json')
    if a.worker:
        try:
            from faster_whisper import WhisperModel
            import importlib.metadata
            model = WhisperModel(str(a.model), device=a.device, compute_type=a.compute_type, local_files_only=True)
            segments, info = model.transcribe(str(a.input), language=a.language, vad_filter=a.vad_filter)
            rows = []
            for segment in segments:
                if len(rows) >= 10000 or len(segment.text) > 4000:
                    raise AudioError('transcript exceeds bounded segment limits')
                rows.append({'start_s': segment.start, 'end_s': segment.end, 'text': segment.text})
            payload = {'segments': rows, 'language': info.language,
                       'faster_whisper_version': importlib.metadata.version('faster-whisper')}
            a.output.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            return
        except ImportError as exc:
            raise AudioError('install a compatible faster-whisper package in the worker environment') from exc
    source = probe(a.input, a.stream, max_seconds=a.max_seconds)
    source_hash, model_digest = digest(source['path']), model_hash(a.model.resolve())
    dest = a.output.absolute()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.transcribe-', dir=dest.parent) as directory:
        pcm, partial = Path(directory) / 'analysis.wav', Path(directory) / 'result.json'
        run(['ffmpeg', '-nostdin', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-i', source['path'],
             '-map', f"0:a:{source['audio_index']}", '-vn', '-ar', '16000', '-ac', '1',
             '-t', str(a.max_seconds + 0.1), '-c:a', 'pcm_s16le', '-n', str(pcm)], a.timeout)
        decoded = probe(pcm, 0, max_seconds=a.max_seconds + 1)
        if decoded['duration_s'] > a.max_seconds or abs(decoded['duration_s'] - source['duration_s']) > .1:
            raise AudioError('decoded duration exceeds limit or does not match source metadata')
        worker = [sys.executable, str(Path(__file__).resolve()), str(pcm), str(partial), '--model', str(a.model.resolve()),
                  '--device', a.device, '--compute-type', a.compute_type, '--language', a.language,
                  '--max-seconds', str(a.max_seconds), '--timeout', str(a.timeout), '--worker']
        if a.vad_filter:
            worker.append('--vad-filter')
        env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
        proc = subprocess.Popen(worker, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, start_new_session=True, env=env)
        try:
            _, err = proc.communicate(timeout=a.timeout)
        except subprocess.TimeoutExpired as exc:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise AudioError('ASR worker timed out') from exc
        if proc.returncode:
            raise AudioError('ASR worker failed: ' + err.decode('utf-8', 'replace')[-2000:])
        result = json.loads(partial.read_text(encoding='utf-8'))
        if digest(source['path']) != source_hash or model_hash(a.model.resolve()) != model_digest:
            raise AudioError('input or model changed while processing')
        result.update({'schema_version': '1.0', 'input_sha256': source_hash, 'model_sha256': model_digest,
                       'audio_stream_index': source['audio_index'], 'device': a.device,
                       'compute_type': a.compute_type, 'vad_filter': a.vad_filter,
                       'warning': 'ASR text may contain hallucinations and is not an intelligibility test'})
        partial.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        os.chmod(partial, 0o600)
        os.link(partial, dest)
    print(json.dumps({'status': 'complete', 'input_sha256': source_hash, 'model_sha256': model_digest,
                      'output_sha256': digest(dest), 'segments': len(result['segments'])}))


if __name__ == '__main__':
    try:
        main()
    except (AudioError, OSError, ValueError, KeyError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
