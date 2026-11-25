"""טמפלייט עריכה — ה"קו האמנותי". אפשר לכתוב ידנית או ללמוד אוטומטית מסרטונים שערכת בעבר."""
import json
import re
import subprocess
from pathlib import Path

import numpy as np

DEFAULT = {
    "name": "default",
    "width": 1080, "height": 1920, "fps": 30,
    # כמה ביטים כל קליפ מחזיק, לפי סוג הקטע בשיר (מחזורי)
    "cut_beats": {"fast": [1, 1, 2], "groove": [2, 2, 4], "artistic": [4, 8]},
    "speed": {"fast": 1.0, "groove": 1.0, "artistic": 0.85},
    "align": {"fast": "peak", "groove": "peak", "artistic": "start"},
    "drop_effect": {"zoom": 1.12, "flash": True},
    "hook_seconds": 1.5,       # הוק פתיחה: ההרמה הכי חזקה בשניות הראשונות
    "max_reuse": 2,             # כמה פעמים מותר להשתמש באותו רגע
    "prefer_lifts_on_downbeat": True,
    "lift_lead": 0.8,          # כמה שניות לפני שיא ההרמה נכנסים (רואים את הכניסה)
    "length": 30,              # אורך הסרטון בשניות (15–45). נבחר הקטע הכי חזק בשיר
}

PRESETS = Path(__file__).resolve().parent.parent / "templates"


def load(path=None):
    t = json.loads(json.dumps(DEFAULT))
    if path:
        f = Path(path)
        if not f.exists():
            f = PRESETS / f"{path}.json"   # שם פריסט: dance / sport
        t.update(json.loads(f.read_text(encoding="utf-8")))
    return t


def learn_from_reference(video_path, threshold=0.3):
    """מזהה חיתוכים בסרטון שערכת ומודד את המרחק שלהם מהביטים -> טמפלייט מותאם אישית."""
    from .audio import analyze_song
    cmd = ["ffmpeg", "-hide_banner", "-i", str(video_path), "-vf",
           f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"]
    err = subprocess.run(cmd, capture_output=True, text=True).stderr
    cuts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", err)]
    song = analyze_song(video_path)
    beats = np.array(song["beats"])
    if len(beats) < 4 or not cuts:
        return {"cuts": cuts, "note": "לא נמצאו מספיק ביטים/חיתוכים"}
    period = 60.0 / song["tempo"]
    off = [float(np.min(np.abs(beats - c))) for c in cuts]
    on_beat = float(np.mean(np.array(off) < 0.08))
    # אורך כל שוט בביטים, לפי סוג הקטע
    bounds = [0.0] + cuts + [song["duration"]]
    per_kind = {"fast": [], "groove": [], "artistic": []}
    for a, b in zip(bounds, bounds[1:]):
        mid = (a + b) / 2
        kind = next((s["kind"] for s in song["sections"] if s["start"] <= mid < s["end"]), "groove")
        per_kind[kind].append(max(1, round((b - a) / period)))
    cut_beats = {}
    for k, v in per_kind.items():
        if v:
            vals, counts = np.unique(v, return_counts=True)
            top = vals[np.argsort(-counts)][:3]
            cut_beats[k] = [int(x) for x in sorted(top)]
    return {
        "source": str(video_path), "tempo": song["tempo"], "num_cuts": len(cuts),
        "cuts_per_second": round(len(cuts) / max(song["duration"], 1), 3),
        "on_beat_ratio": round(on_beat, 3),
        "avg_shot_beats": round(float(np.mean(sum(per_kind.values(), []))), 2),
        "cut_beats": cut_beats,
    }


def merge_learned(learned_list):
    t = load()
    agg = {"fast": [], "groove": [], "artistic": []}
    for L in learned_list:
        for k, v in L.get("cut_beats", {}).items():
            agg[k] += v
    for k, v in agg.items():
        if v:
            t["cut_beats"][k] = sorted(set(v))[:3]
    t["name"] = "learned"
    t["learned_from"] = [L.get("source") for L in learned_list]
    return t
