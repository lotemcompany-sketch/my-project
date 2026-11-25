"""ניתוח קליפים: תנועה, חדות, "רגעי שיא" (הרמות/תנועות חזקות) וסגנון (מהיר/אומנותי)."""
import cv2
import numpy as np

SAMPLE_FPS = 10


def analyze_clip(path):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    step = max(1, int(round(fps / SAMPLE_FPS)))
    prev = None
    motion, vertical, sharp, bright, times = [], [], [], [], []
    idx = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            g = cv2.cvtColor(cv2.resize(frame, (160, int(160 * h / max(w, 1)) or 90)), cv2.COLOR_BGR2GRAY)
            sharp.append(float(cv2.Laplacian(g, cv2.CV_64F).var()))
            bright.append(float(g.mean()))
            if prev is not None:
                flow = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 2, 9, 2, 5, 1.1, 0)
                mag = np.linalg.norm(flow, axis=2)
                motion.append(float(mag.mean()))
                # תנועה כלפי מעלה (y שלילי) — אינדיקציה להרמה/קפיצה
                vertical.append(float(max(0.0, -flow[..., 1][mag > np.percentile(mag, 80)].mean() if mag.size else 0)))
            else:
                motion.append(0.0); vertical.append(0.0)
            times.append(idx / fps)
            prev = g
        idx += 1
    cap.release()
    duration = n / fps if n else (times[-1] if times else 0)
    return {
        "path": str(path), "fps": fps, "width": w, "height": h, "duration": round(duration, 3),
        "times": [round(t, 2) for t in times],
        "motion": _smooth(motion), "vertical": _smooth(vertical),
        "sharpness": sharp, "brightness": bright,
    }


def _smooth(a, k=3):
    a = np.array(a, dtype=float)
    if a.size < k:
        return a.round(4).tolist()
    return np.convolve(a, np.ones(k) / k, mode="same").round(4).tolist()


def find_moments(clip, min_len=0.6, max_len=6.0):
    """מוצא רגעים חזקים בקליפ: פיקים של תנועה/הרמה + קטעים רציפים זורמים."""
    t = np.array(clip["times"]); m = np.array(clip["motion"]); v = np.array(clip["vertical"])
    s = np.array(clip["sharpness"]); b = np.array(clip["brightness"])
    if t.size < 5:
        return []
    norm = lambda a: (a - a.min()) / (np.ptp(a) or 1)
    mn, vn, sn = norm(m), norm(v), norm(np.log1p(s))
    exposure = 1 - np.abs(b - 128) / 128  # תמונה לא שרופה/חשוכה
    quality = 0.6 * sn + 0.4 * exposure
    moments = []
    # 1) פיקים (מתאימים לחיתוך על דאון-ביט / דרופ)
    from scipy.signal import find_peaks
    peaks, _ = find_peaks(mn + 0.8 * vn, distance=max(1, int(SAMPLE_FPS * 1.0)), prominence=0.15)
    for p in peaks:
        moments.append({
            "clip": clip["path"], "peak": float(t[p]),
            "start": float(max(0, t[p] - 1.5)), "end": float(min(clip["duration"], t[p] + 1.5)),
            "energy": round(float(mn[p]), 3), "lift": round(float(vn[p]), 3),
            "quality": round(float(quality[p]), 3), "style": "fast" if mn[p] > 0.5 else "groove",
        })
    # 2) קטעים רגועים וזורמים (אומנותי) — תנועה בינונית-נמוכה ויציבה
    win = int(SAMPLE_FPS * 3)
    for i in range(0, len(t) - win, win // 2):
        seg = mn[i:i + win]
        if 0.08 < seg.mean() < 0.45 and seg.std() < 0.2:
            moments.append({
                "clip": clip["path"], "peak": float(t[i + win // 2]),
                "start": float(t[i]), "end": float(t[i + win - 1]),
                "energy": round(float(seg.mean()), 3), "lift": round(float(vn[i:i + win].max()), 3),
                "quality": round(float(quality[i:i + win].mean()), 3), "style": "artistic",
            })
    for mo in moments:
        mo["score"] = round(0.45 * mo["energy"] + 0.35 * mo["lift"] + 0.2 * mo["quality"]
                            if mo["style"] != "artistic" else 0.5 * mo["quality"] + 0.3 * mo["lift"] + 0.2 * (1 - mo["energy"]), 3)
    return sorted(moments, key=lambda x: -x["score"])
