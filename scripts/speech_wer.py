#!/usr/bin/env python3
"""Compute normalized word-error rate against a supplied reference transcript."""
import argparse
import json
import math
from pathlib import Path
import re
import sys
import unicodedata


def words(path):
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('transcript exceeds 8 MiB limit')
    text = path.read_text(encoding='utf-8')
    result = re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold(), re.UNICODE)
    if len(result) > 10000:
        raise ValueError('transcript exceeds 10,000 word limit')
    return result


def distance(reference, hypothesis):
    # O(min(N,M)) memory; Levenshtein is symmetric for the distance used in WER.
    if len(hypothesis) > len(reference):
        reference, hypothesis = hypothesis, reference
    previous = list(range(len(hypothesis) + 1))
    for i, word in enumerate(reference, 1):
        current = [i]
        for j, other in enumerate(hypothesis, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j-1] + (word != other)))
        previous = current
    return previous[-1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('reference', type=Path)
    p.add_argument('hypothesis', type=Path)
    p.add_argument('--warning-wer', type=float, default=0.2)
    a = p.parse_args()
    if not math.isfinite(a.warning_wer) or a.warning_wer < 0:
        p.error('warning threshold must be finite and non-negative')
    ref, hyp = words(a.reference), words(a.hypothesis)
    if not ref:
        p.error('reference transcript must contain words')
    if len(ref) * len(hyp) > 4_000_000:
        p.error('transcripts too long for bounded comparison; segment and aggregate edit counts')
    errors = distance(ref, hyp)
    wer = errors / len(ref)
    print(json.dumps({'schema_version': '1.0', 'reference_words': len(ref), 'hypothesis_words': len(hyp),
        'word_edits': errors, 'wer': round(wer, 6), 'warning_threshold': a.warning_wer,
        'status': 'indeterminate' if len(ref) < 5 else ('warning' if wer > a.warning_wer else 'pass'),
        'warning': 'WER depends on reference, language, transcription model and normalization; not proof of intelligibility'},
        ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, UnicodeError, ValueError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
