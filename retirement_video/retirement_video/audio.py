from __future__ import annotations

import hashlib
import json
from pathlib import Path


def analyze_music(path: str | Path, cache_dir: str | Path) -> dict:
    import librosa

    path = Path(path)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(f"{path.resolve()}:{path.stat().st_size}:{path.stat().st_mtime_ns}".encode()).hexdigest()
    cache = cache_dir / f"{fingerprint}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    signal, rate = librosa.load(path, sr=22050, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=signal, sr=rate)
    beat_times = librosa.frames_to_time(beat_frames, sr=rate).tolist()
    rms = librosa.feature.rms(y=signal)[0]
    times = librosa.times_like(rms, sr=rate)
    energy = [{"time": round(float(t), 3), "value": round(float(v), 6)} for t, v in zip(times[::8], rms[::8])]
    result = {
        "bpm": round(float(tempo.item() if hasattr(tempo, "item") else tempo), 2),
        "beats": [round(float(x), 3) for x in beat_times],
        "energy": energy,
        "duration": round(float(librosa.get_duration(y=signal, sr=rate)), 3),
    }
    cache.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result
