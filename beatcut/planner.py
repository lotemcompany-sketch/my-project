"""בונה טיימליין: כל קליפ מתחיל ונגמר בדיוק על ביט, הרגע החזק נוחת על הדאון-ביט."""
import bisect


def build_timeline(song, moments, tpl, locked=None, seed=0):
    import random
    rng = random.Random(seed)
    jitter = {id(m): (rng.random() - 0.5) * 0.25 if seed else 0.0 for m in moments}
    beats = song["beats"]
    w0, w1 = song.get("window", [0, len(beats)])
    if not beats:
        raise ValueError("לא זוהו ביטים בשיר")
    downbeats = set(song["downbeats"])
    locked = {s["start_beat"]: s for s in (locked or [])}
    perf = song.get("_perf", {})   # clip -> [(t0, t1, offset)] סנכרון לציר ההופעה
    used_perf = []                 # רגעים בריקוד שכבר הוצגו (מכל זווית)
    use_count = {}
    used = {}   # clip -> [(a, b)] טווחים שכבר נוצלו מהצילום
    clip_uses = {}
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
        mo, src_in = _pick(moments, kind, dur * speed, used, clip_uses, tpl, want_lift,
                           segs[-1]["clip"] if segs else None, jitter, perf, used_perf)
        if mo is None:
            break
        used.setdefault(mo["clip"], []).append((src_in, src_in + dur * speed))
        used_perf.extend(_perf_span(perf.get(mo["clip"], []), src_in, src_in + dur * speed))
        clip_uses[mo["clip"]] = clip_uses.get(mo["clip"], 0) + 1
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


def _in_point(mo, need, tpl, kind):
    align = tpl["align"][kind]
    if align == "peak" or mo["style"] != "artistic":
        # בהרמה נכנסים קצת לפני השיא כדי לראות את הכניסה; השיא נוחת בתוך החיתוך
        lead = tpl.get("lift_lead", 0.25) if mo["lift"] > 0.4 else 0.25
        src_in = mo["peak"] - min(lead, need * 0.6)
    else:
        src_in = mo["start"]
    return max(0.0, min(src_in, mo["clip_duration"] - need - 0.05))


def _perf_span(segs, a, b, step=0.25):
    """טווחי זמן-הופעה שהחלק [a,b] בקליפ מכסה."""
    out = []
    t = a
    while t <= b:
        for t0, t1, off in segs:
            if t0 <= t < t1:
                out.append((t + off - step, t + off + step))
                break
        t += step
    return out


def _overlaps(a, b, ranges, gap=0.6):
    return any(a < y + gap and b > x - gap for x, y in ranges)


def _pick(moments, kind, need, used, clip_uses, tpl, want_lift, last_clip=None, jitter=None, perf=None, used_perf=None):
    """בוחר את הרגע הכי טוב שעוד לא נוצל: אף שנייה מהצילום לא חוזרת, ומפזרים בין כל הקליפים."""
    style_ok = {"fast": ("fast", "groove"), "groove": ("groove", "fast", "artistic"), "artistic": ("artistic", "groove")}[kind]
    n_clips = max(1, len({m["clip"] for m in moments if m.get("clip_quality", 1) >= 0.5}))
    total = sum(clip_uses.values())
    best, best_in, best_v = None, None, -1e9
    for mo in moments:
        if mo["clip_duration"] < need + 0.05:
            continue
        src_in = _in_point(mo, need, tpl, kind)
        if _overlaps(src_in, src_in + need, used.get(mo["clip"], [])):
            continue
        if perf and perf.get(mo["clip"]):
            span = _perf_span(perf[mo["clip"]], src_in, src_in + need, 0.5)
            if not span:
                continue  # לא יודעים איזה רגע בריקוד זה, אז לא מסתכנים בחזרה
            if used_perf and any(_overlaps(x, y, used_perf, gap=0.8) for x, y in span):
                continue  # אותו רגע בריקוד כבר הוצג מזווית אחרת
        cq = mo.get("clip_quality", 1.0)
        if cq < 0.5 and clip_uses.get(mo["clip"], 0) >= tpl.get("max_far_uses", 1):
            continue  # צילום רחוק/חשוך: לכל היותר פעם אחת (פתיח רחב)
        v = mo["score"] + 0.9 * cq + (jitter or {}).get(id(mo), 0.0)
        v += 0.3 if mo["style"] == kind else (0.0 if mo["style"] in style_ok else -0.6)
        if want_lift:
            v += 0.6 * mo["lift"]
        if mo["clip"] == last_clip:
            v -= 0.5  # לא אותו קליפ פעמיים ברצף
        # פיזור: קליפ שכבר השתמשנו בו הרבה יחסית לאחרים מקבל קנס
        share = clip_uses.get(mo["clip"], 0) - total / n_clips
        v -= 0.12 * max(0.0, share)
        if v > best_v:
            best, best_in, best_v = mo, src_in, v
    return best, best_in
