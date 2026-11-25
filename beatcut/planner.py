"""בונה טיימליין: כל קליפ מתחיל ונגמר בדיוק על ביט, הרגע החזק נוחת על הדאון-ביט."""
import bisect


def build_timeline(song, moments, tpl, locked=None):
    beats = song["beats"]
    w0, w1 = song.get("window", [0, len(beats)])
    if not beats:
        raise ValueError("לא זוהו ביטים בשיר")
    downbeats = set(song["downbeats"])
    locked = {s["start_beat"]: s for s in (locked or [])}
    use_count = {}
    segs = []
    i = w0
    cycle = {}
    grid = beats + [song["duration"]]
    while i < w1:
        t0 = beats[i]
        sec = _section_at(song["sections"], t0)
        kind = sec["kind"]
        if i in locked:
            s = dict(locked[i]); segs.append(s); i = s["start_beat"] + s["beats"]; continue
        opts = tpl["cut_beats"][kind]
        n = opts[cycle.get(kind, 0) % len(opts)]; cycle[kind] = cycle.get(kind, 0) + 1
        # מעגלים לדאון-ביט הבא כדי שהחיתוכים הגדולים ייפלו על תחילת תיבה
        n = min(n, w1 - i)
        nxt = next((L for L in locked if i < L < i + n), None)
        if nxt is not None:
            n = nxt - i
        t1 = grid[i + n]
        dur = t1 - t0
        speed = tpl["speed"][kind]
        is_hook = t0 - beats[w0] < tpl["hook_seconds"] and not segs
        on_drop = bool(sec.get("drop")) and abs(sec["start"] - t0) < 0.05
        want_lift = is_hook or on_drop or (tpl["prefer_lifts_on_downbeat"] and t0 in downbeats and kind != "artistic")
        mo = _pick(moments, kind, dur * speed, use_count, tpl["max_reuse"], want_lift, segs[-1]["clip"] if segs else None)
        if mo is None:
            break
        key = (mo["clip"], mo["peak"]); use_count[key] = use_count.get(key, 0) + 1
        align = tpl["align"][kind]
        src_in = mo["peak"] if align == "peak" else mo["start"]
        # בפיק: מתחילים קצת לפני כדי שהשיא ייראה מיד עם הביט
        if align == "peak":
            # בהרמה נכנסים קצת לפני השיא כדי לראות את הכניסה; השיא נוחת בתוך החיתוך
            lead = tpl.get("lift_lead", 0.25) if mo["lift"] > 0.4 else 0.25
            src_in = max(0.0, mo["peak"] - min(lead, dur * speed * 0.6))
        src_in = max(0.0, min(src_in, mo["clip_duration"] - dur * speed - 0.05))
        segs.append({
            "start_beat": i, "beats": n, "start": round(t0, 3), "end": round(t1, 3),
            "kind": kind, "clip": mo["clip"], "in": round(src_in, 3), "speed": speed,
            "moment_score": mo["score"], "lift": mo["lift"],
            "fx": {"zoom": tpl["drop_effect"]["zoom"] if on_drop else 1.0,
                   "flash": bool(tpl["drop_effect"]["flash"] and on_drop)},
            "hook": is_hook, "locked": False,
        })
        i += n
    return segs


def _section_at(sections, t):
    for s in sections:
        if s["start"] - 1e-3 <= t < s["end"]:
            return s
    return sections[-1]


def _pick(moments, kind, need, use_count, max_reuse, want_lift, last_clip=None):
    style_ok = {"fast": ("fast", "groove"), "groove": ("groove", "fast", "artistic"), "artistic": ("artistic", "groove")}[kind]
    best, best_v = None, -1e9
    for mo in moments:
        if mo["clip_duration"] < need + 0.05:
            continue
        u = use_count.get((mo["clip"], mo["peak"]), 0)
        if u >= max_reuse:
            continue
        v = mo["score"] - 0.5 * u
        v += 0.3 if mo["style"] == kind else (0.0 if mo["style"] in style_ok else -0.6)
        if mo["clip"] == last_clip:
            v -= 0.4  # לא אותו קליפ פעמיים ברצף
        if want_lift:
            v += 0.6 * mo["lift"]
        if v > best_v:
            best, best_v = mo, v
    return best
