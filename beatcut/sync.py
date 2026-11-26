"""סנכרון כל הצילומים לציר זמן אחד של ההופעה, לפי הסאונד המשותף.
כך יודעים שאותו רגע בריקוד צולם בכמה קבצים, ולא מראים אותו פעמיים."""
import numpy as np
import librosa

from .audio import _load

SR, HOP = 11025, 256
FPS = SR / HOP


def envelope(path):
    y, _ = _load(path, SR)
    if y.size == 0:
        return np.zeros(1)
    e = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    e = (e - e.mean()) / (e.std() or 1)
    return e


def _match(win, ref):
    """מיקום הטוב ביותר של חלון בתוך הרפרנס + ציון ביטחון (z)."""
    n = len(win)
    if n < 20 or len(ref) < n:
        return None, 0.0
    L = 1 << int(np.ceil(np.log2(len(ref) + n)))
    c = np.fft.irfft(np.fft.rfft(ref, L) * np.conj(np.fft.rfft(win, L)), L)[: len(ref) - n + 1]
    # נרמול לפי האנרגיה המקומית של הרפרנס
    cs = np.concatenate([[0], np.cumsum(ref ** 2)])
    local = np.sqrt(np.maximum(cs[n:] - cs[:-n], 1e-9))
    c = c / (local * np.linalg.norm(win) + 1e-9)
    k = int(np.argmax(c))
    z = (c[k] - c.mean()) / (c.std() or 1)
    return k / FPS, float(z)


def sync_clips(paths, win_s=6.0, step_s=3.0, zmin=7.0, log=print):
    """מחזיר לכל קליפ רשימה של (t0, t1, perf_offset): זמן ההופעה = t + offset."""
    envs = {p: envelope(p) for p in paths}
    order = sorted(paths, key=lambda p: -len(envs[p]))
    ref = order[0]
    maps = {ref: [(0.0, len(envs[ref]) / FPS, 0.0)]}
    known = {ref: 0.0}  # קליפים ארוכים עם היסט קבוע ידוע
    for p in order[1:]:
        e = envs[p]; n = int(win_s * FPS); st = int(step_s * FPS)
        segs, votes = [], []
        for i in range(0, max(1, len(e) - n + 1), st):
            w = e[i:i + n]
            best = None
            for r, roff in known.items():
                lag, z = _match(w, envs[r])
                if lag is not None and z >= zmin and (best is None or z > best[1]):
                    best = (lag + roff - i / FPS, z)
            if best:
                segs.append((i / FPS, (i + n) / FPS, round(best[0], 3)))
                votes.append(round(best[0], 1))
        maps[p] = segs
        if votes:
            vals, cnt = np.unique(votes, return_counts=True)
            if cnt.max() >= 0.7 * len(votes) and len(votes) >= 5:
                known[p] = float(vals[np.argmax(cnt)])  # קליפ רציף: אפשר להשתמש בו כרפרנס נוסף
        log(f"sync {p.split('/')[-1]}: {len(segs)}/{max(1, (len(e) - n) // st + 1)} windows matched")
    return maps


def perf_time(segs, t):
    """ממיר זמן בקליפ לזמן בהופעה (או None אם לא סונכרן)."""
    for t0, t1, off in segs:
        if t0 <= t < t1:
            return t + off
    return None


def _hashes(path, fps=2.0):
    """טביעת אצבע חזותית (dHash 64 ביט) לכל פריים, פעמיים בשנייה."""
    import cv2
    cap = cv2.VideoCapture(str(path)); vf = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(round(vf / fps))); out = []; i = 0
    while cap.grab():
        if i % step == 0:
            ok, f = cap.retrieve()
            if not ok:
                break
            g = cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (9, 8), interpolation=cv2.INTER_AREA)
            out.append((i / vf, np.packbits((g[:, 1:] > g[:, :-1]).flatten())))
        i += 1
    cap.release()
    return out


def _covered(segs):
    return sum(b - a for a, b, _ in segs)


def visual_fill(maps, paths, durations, maxdist=10, log=print):
    """לקליפים ערוכים (בלי סאונד רציף): מוצא כל פריים בצילומים המסונכרנים לפי מראה."""
    maps = {p: [tuple(x) for x in maps.get(p, [])] for p in paths}
    synced = {p for p in paths if _covered(maps[p]) >= 0.4 * durations[p]}
    pool = []
    for p in paths:
        if p in synced:
            for t, h in _hashes(p):
                pt = perf_time(maps[p], t)
                if pt is not None:
                    pool.append((pt, h))
    if not pool:
        return maps
    H = np.array([np.unpackbits(h) for _, h in pool]); T = np.array([t for t, _ in pool])
    for p in paths:
        if p in synced:
            continue
        segs = list(maps[p]); hit = 0
        for t, h in _hashes(p):
            if perf_time(segs, t) is not None:
                continue
            d = (H != np.unpackbits(h)).sum(1); k = int(np.argmin(d))
            if d[k] <= maxdist:
                segs.append((t - 0.25, t + 0.25, round(float(T[k] - t), 3))); hit += 1
        maps[p] = sorted(segs)
        log(f"visual {p.split('/')[-1]}: {hit} frames matched")
    return maps
