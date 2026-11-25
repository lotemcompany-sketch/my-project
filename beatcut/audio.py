"""ניתוח השיר: ביטים, דאון-ביטים, אנרגיה וחלוקה לקטעים (שקט/אומנותי מול מהיר/דרופ)."""
import numpy as np
import librosa


def analyze_song(path, sr=22050):
    y, sr = librosa.load(path, sr=sr, mono=True)
    duration = len(y) / sr
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, units="frames")
    tempo = float(np.atleast_1d(tempo)[0])
    beats = librosa.frames_to_time(beat_frames, sr=sr)
    # משלימים את רשת הביטים אחורה עד תחילת השיר (אינטרו שקט), כדי שהטיימליין יתחיל ב-0
    period = 60.0 / tempo if tempo > 0 else 0.5
    pre = []
    if len(beats):
        t = beats[0] - period
        while t > 0.05:
            pre.insert(0, t); t -= period
        beats = np.concatenate([[0.0], pre, beats]) if beats[0] > 0.05 else beats
        beat_frames = librosa.time_to_frames(beats, sr=sr)

    # דאון-ביט: בוחרים את הפאזה (0..3) שבה עוצמת האונסט הממוצעת הכי גבוהה
    strengths = onset_env[np.clip(beat_frames, 0, len(onset_env) - 1)] if len(beat_frames) else np.array([])
    phase = 0
    if len(strengths) >= 8:
        phase = int(np.argmax([strengths[p::4].mean() for p in range(4)]))
    downbeats = beats[phase::4]

    # אנרגיה לכל ביט (RMS) — מנורמל 0..1
    rms = librosa.feature.rms(y=y)[0]
    rms_t = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    beat_energy = []
    edges = list(beats) + [duration]
    for i in range(len(beats)):
        m = (rms_t >= edges[i]) & (rms_t < edges[i + 1])
        beat_energy.append(float(rms[m].mean()) if m.any() else 0.0)
    be = np.array(beat_energy)
    if be.size and be.max() > be.min():
        be = (be - be.min()) / (be.max() - be.min())
    beat_energy = be.tolist()

    sections = _sections(beats, downbeats, beat_energy, duration)

    # וייברפורם מוקטן לדשבורד
    hop = max(1, len(y) // 1500)
    wave = np.abs(y[: hop * (len(y) // hop)]).reshape(-1, hop).max(axis=1)
    wave = (wave / (wave.max() or 1)).round(3).tolist()

    return {
        "path": str(path),
        "duration": round(duration, 3),
        "tempo": round(tempo, 2),
        "beats": [round(float(b), 3) for b in beats],
        "downbeats": [round(float(b), 3) for b in downbeats],
        "beat_energy": [round(e, 3) for e in beat_energy],
        "sections": sections,
        "waveform": wave,
    }


def _sections(beats, downbeats, energy, duration, bar_group=4):
    """מקבץ ריבועי תיבות (4 תיבות = 16 ביטים) ומסווג לפי אנרגיה."""
    if len(beats) == 0:
        return [{"start": 0.0, "end": duration, "kind": "artistic", "energy": 0.0}]
    e = np.array(energy)
    hi, lo = np.percentile(e, 66), np.percentile(e, 33)
    step = bar_group * 4
    out = []
    for i in range(0, len(beats), step):
        seg = e[i : i + step]
        start = float(beats[i])
        end = float(beats[i + step]) if i + step < len(beats) else duration
        m = float(seg.mean())
        kind = "fast" if m >= hi else ("artistic" if m <= lo else "groove")
        if out and out[-1]["kind"] == kind:
            out[-1]["end"] = round(end, 3)
            out[-1]["energy"] = round((out[-1]["energy"] + m) / 2, 3)
        else:
            out.append({"start": round(start, 3), "end": round(end, 3), "kind": kind, "energy": round(m, 3)})
    # דרופ = מעבר חד מאנרגיה נמוכה לגבוהה
    for a, b in zip(out, out[1:]):
        if (b["kind"] == "fast" and a["kind"] != "fast") or b["energy"] - a["energy"] > 0.25:
            b["drop"] = True
    return out
