"""Read a 16-bit mono WAV, and measure it in frames, with numpy when the owner's venv has it and plain Python if not.

The voice activity pass and the waveform peaks both need a level per short frame over tens of millions of samples.
numpy does that in a second. The plain-Python path is slow, but it's correct, and the tests use short files with it.
"""
import math
import wave
from array import array


def read(path):
    """(raw 16-bit sample bytes, sample rate) from a mono WAV."""
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError(f"{path}: expected 16-bit mono, got {w.getnchannels()} channels of {w.getsampwidth() * 8} bits")
        return w.readframes(w.getnframes()), w.getframerate()


def frame_levels(raw, rate, frame_s, kind="rms"):
    """One level per frame, either RMS or peak, as fractions of full scale (0.0 to 1.0)."""
    n = max(1, int(rate * frame_s))
    try:
        import numpy as np
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        k = len(x) // n
        if k == 0:
            return []
        x = x[:k * n].reshape(k, n)
        vals = np.sqrt((x ** 2).mean(axis=1)) if kind == "rms" else np.abs(x).max(axis=1)
        return [float(v) for v in vals]
    except ImportError:
        a = array("h")
        a.frombytes(raw)
        out = []
        for i in range(0, len(a) - n + 1, n):
            chunk = a[i:i + n]
            if kind == "rms":
                out.append(math.sqrt(sum(v * v for v in chunk) / n) / 32768.0)
            else:
                out.append(max(abs(v) for v in chunk) / 32768.0)
        return out


def db(level):
    return 20.0 * math.log10(level + 1e-9)
