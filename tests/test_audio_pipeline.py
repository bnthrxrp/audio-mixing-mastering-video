"""Executable integration tests with synthetic signals and the real FFmpeg binary."""
import json
import math
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
RATE = 48000


def wav(path, fn, seconds=4):
    with wave.open(str(path), 'wb') as w:
        w.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        data = bytearray()
        for i in range(RATE * seconds):
            value = max(-1, min(1, fn(i / RATE, i)))
            data.extend(struct.pack('<h', round(value * 32767)))
        w.writeframes(data)


def script(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                          text=True, capture_output=True, timeout=90)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='audio tests ')
        self.p = Path(self.tmp.name)
        self.tone = self.p / 'tone with spaces.wav'
        wav(self.tone, lambda t, i: .12 * math.sin(2 * math.pi * 1000 * t))

    def tearDown(self):
        self.tmp.cleanup()

    def test_qc_reports_full_scale_and_no_false_intelligibility(self):
        source = self.p / 'clipped.wav'
        wav(source, lambda t, i: 1 if 1 < t < 1.1 else (.15 * math.sin(2 * math.pi * 300 * t) if t > 2 else 0))
        result = script('audio_qc.py', source)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['checks']['clipping']['status'], 'warning')
        self.assertEqual(report['checks']['intelligibility']['status'], 'indeterminate')
        self.assertEqual(report['objective_gate'], 'indeterminate')
        self.assertGreater(report['checks']['silence']['evidence']['fraction'], .2)

    def test_strict_missing_targets_is_not_pass(self):
        result = script('audio_qc.py', self.tone, '--strict')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)['objective_gate'], 'indeterminate')

    def test_normalize_independent_qc_and_no_overwrite(self):
        output = self.p / 'normalized.wav'
        result = script('normalize_loudness.py', self.tone, output, '--target-i', '-5', '--target-tp', '-9', '--target-lra', '11')
        self.assertNotEqual(result.returncode, 0)  # linear gain cannot reach this loudness without violating the peak limit
        self.assertFalse(output.exists())
        result = script('normalize_loudness.py', self.tone, output, '--target-i', '-20', '--target-tp', '-2', '--target-lra', '11', '--allow-dynamic')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['numeric_qc'], 'pass')
        self.assertLessEqual(report['after_ebur128']['true_peak_dbtp'], -2)
        result = script('audio_qc.py', output, '--target-i', '-20', '--target-tp', '-2', '--strict')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        result = script('normalize_loudness.py', self.tone, output, '--target-i', '-20', '--target-tp', '-2', '--target-lra', '11')
        self.assertNotEqual(result.returncode, 0)

    def test_silence_cannot_be_normalized(self):
        source, output = self.p / 'silent.wav', self.p / 'silent-out.wav'
        wav(source, lambda t, i: 0)
        result = script('normalize_loudness.py', source, output, '--target-i', '-20', '--target-tp', '-2', '--target-lra', '11')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_linear_normalization_is_supported(self):
        source, output = self.p / 'dynamic-content.wav', self.p / 'linear.wav'
        wav(source, lambda t, i: (.04 if t < 6 else .20) * math.sin(2 * math.pi * 500 * t), seconds=12)
        result = script('normalize_loudness.py', source, output, '--target-i', '-20', '--target-tp', '-2', '--target-lra', '20')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['mode'], 'linear')

    def test_mono_and_dual_mono_are_distinct(self):
        regular = script('audio_qc.py', self.tone)
        dual = script('audio_qc.py', self.tone, '--dual-mono')
        self.assertEqual(regular.returncode, 0, regular.stderr)
        self.assertEqual(dual.returncode, 0, dual.stderr)
        before = json.loads(regular.stdout)['measurements']['loudness']['integrated_lufs']
        after = json.loads(dual.stdout)['measurements']['loudness']['integrated_lufs']
        self.assertAlmostEqual(after - before, 3, delta=.2)

    def test_duck_is_bounded_and_stems_are_required(self):
        voice, music, out = self.p / 'voice.wav', self.p / 'music.wav', self.p / 'duck.wav'
        wav(voice, lambda t, i: .18 * math.sin(2 * math.pi * 500 * t) if 1 < t < 3.5 else 0)
        wav(music, lambda t, i: .14 * math.sin(2 * math.pi * 200 * t))
        result = script('audio_qc.py', music, '--voice-stem', voice, '--music-stem', music, '--stems-synchronized')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['checks']['music_masking']['status'], 'warning')
        result = script('correct_audio.py', 'duck', voice, music, out, '--stems-synchronized')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertLess(report['qc']['active_median_change_db'], -.5)
        self.assertTrue(out.exists())
        mismatch = self.p / 'short.wav'
        wav(mismatch, lambda t, i: .1 * math.sin(t), seconds=2)
        bad = self.p / 'bad.wav'
        result = script('correct_audio.py', 'duck', voice, mismatch, bad, '--stems-synchronized')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(bad.exists())

    def test_denoise_checked_before_promotion(self):
        rng = random.Random(123)
        voice, out = self.p / 'noisy.wav', self.p / 'clean.wav'
        wav(voice, lambda t, i: rng.uniform(-.013, .013) + (.14 * math.sin(2 * math.pi * 600 * t) if 1 < t < 3 else 0))
        result = script('correct_audio.py', 'denoise', voice, out, '--noise-confirmed', '--noise-floor-dbfs', '-40')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLessEqual(json.loads(result.stdout)['qc']['nonvoice_median_change_db'], -1)
        self.assertTrue(out.exists())

    def test_voice_gain_rejects_excessive_true_peak(self):
        output = self.p / 'gained.wav'
        good = script('gain_voice.py', self.tone, output, '--isolated-voice', '--gain-db', '3', '--target-tp', '-2')
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout)['numeric_qc'], 'pass')
        bad_output = self.p / 'rejected.wav'
        bad = script('gain_voice.py', self.tone, bad_output, '--isolated-voice', '--gain-db', '6', '--target-tp', '-20')
        self.assertNotEqual(bad.returncode, 0)
        self.assertFalse(bad_output.exists())

    def test_bad_stream_and_nonexistent_file_fail_cleanly(self):
        self.assertNotEqual(script('audio_qc.py', self.p / 'missing.wav').returncode, 0)
        self.assertNotEqual(script('audio_qc.py', self.tone, '--stream', '4').returncode, 0)
        self.assertNotEqual(script('audio_qc.py', self.tone, '--target-i', 'nan').returncode, 0)
        broken = self.p / 'corrupt.wav'
        broken.write_bytes(b'not a real wave file')
        self.assertNotEqual(script('audio_qc.py', broken).returncode, 0)

    def test_multiple_streams_require_explicit_selection(self):
        container = self.p / 'two-tracks.mkv'
        create = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(self.tone), '-i', str(self.tone),
            '-map', '0:a:0', '-map', '1:a:0', '-c:a', 'flac', str(container)], capture_output=True)
        self.assertEqual(create.returncode, 0, create.stderr.decode(errors='replace'))
        self.assertNotEqual(script('audio_qc.py', container).returncode, 0)
        selected = script('audio_qc.py', container, '--stream', '1')
        self.assertEqual(selected.returncode, 0, selected.stderr)
        self.assertEqual(json.loads(selected.stdout)['stream']['audio_index'], 1)

    def test_wer_uses_reference_length_and_normalizes_case(self):
        ref, hyp = self.p / 'ref.txt', self.p / 'hyp.txt'
        ref.write_text('Olá Maria como vai você hoje', encoding='utf-8')
        hyp.write_text('olá MARIA como vai você amanhã', encoding='utf-8')
        result = script('speech_wer.py', ref, hyp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertAlmostEqual(json.loads(result.stdout)['wer'], 1/6, places=5)

    def test_batch_is_content_addressed_and_idempotent(self):
        input_dir, output_dir = self.p / 'input', self.p / 'output'
        input_dir.mkdir()
        shutil.copy(self.tone, input_dir / 'audio.wav')
        first = script('batch_qc.py', input_dir, output_dir, '--jobs', '2')
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout.splitlines()[0])['state'], 'complete')
        second = script('batch_qc.py', input_dir, output_dir, '--jobs', '2')
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout.splitlines()[0])['state'], 'cached')
        self.assertEqual(len(list(output_dir.glob('*.json'))), 1)

    def test_transcription_wrapper_with_stub_model(self):
        # Exercises isolation, stream extraction, timeout wrapper and atomic JSON, not ASR accuracy.
        site, model = self.p / 'stub-site', self.p / 'model'
        site.mkdir()
        model.mkdir()
        for name in ('model.bin', 'config.json', 'tokenizer.json'):
            (model / name).write_text('fixture', encoding='utf-8')
        (site / 'faster_whisper.py').write_text('''\
from types import SimpleNamespace
class WhisperModel:
    def __init__(self, path, **kwargs):
        assert kwargs['local_files_only'] is True
    def transcribe(self, path, **kwargs):
        return iter([SimpleNamespace(start=0.0, end=1.0, text='olá')]), SimpleNamespace(language='pt')
''', encoding='utf-8')
        dist = site / 'faster_whisper-1.0.dist-info'
        dist.mkdir()
        (dist / 'METADATA').write_text('Name: faster-whisper\nVersion: 1.0\n', encoding='utf-8')
        output = self.p / 'transcript.json'
        env = dict(os.environ, PYTHONPATH=str(site))
        result = subprocess.run([sys.executable, str(SCRIPTS / 'transcribe_local.py'), str(self.tone), str(output),
                                 '--model', str(model)], env=env, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['segments'][0]['text'], 'olá')
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
