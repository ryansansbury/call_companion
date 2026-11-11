"""The owner's machine only. Give a buyer's track the sound of a phone line.

The track goes through ffmpeg's band-pass to the 300 to 3,400 Hz a phone line carries, then a round trip through an
8 kHz mu-law codec, and comes back at 24 kHz with a light seeded hiss under it. The seller sits on a headset and
keeps the clean sound, the way a rep's softphone call usually records.
"""
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

RATE = 24000


def run(args):
    done = subprocess.run(args, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + (done.stderr.strip().splitlines() or ["no message"])[-1])


def phone_line(src, dst, seed=0, noise_db=-56.0):
    """Write dst as src heard down a phone line. Safe when src and dst are the same file."""
    with tempfile.TemporaryDirectory() as tmp:
        narrow = Path(tmp).joinpath("narrow.wav")
        back = Path(tmp).joinpath("back.wav")
        run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", "highpass=f=300,lowpass=f=3400",
             "-ar", "8000", "-ac", "1", "-c:a", "pcm_mulaw", str(narrow)])
        run(["ffmpeg", "-v", "error", "-y", "-i", str(narrow), "-ar", str(RATE), "-ac", "1",
             "-c:a", "pcm_s16le", str(back)])
        audio, rate = sf.read(back, dtype="float32")
    rng = np.random.default_rng(seed)
    hiss = rng.standard_normal(len(audio)).astype(np.float32)
    hiss = np.convolve(hiss, np.ones(8, dtype=np.float32) / 8, mode="same")
    hiss *= (10 ** (noise_db / 20)) / (float(np.sqrt(np.mean(hiss ** 2))) + 1e-12)
    sf.write(dst, np.clip(audio + hiss, -1.0, 1.0), rate, subtype="PCM_16")
