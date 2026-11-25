"""מקשר הכל: מנתח שיר + קליפים, בונה פרויקט JSON שהדשבורד קורא וכותב."""
import json
import subprocess
from pathlib import Path

from . import audio, video, planner, template

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}


def create(song_path, clips_dir, out_dir, template_path=None, log=print, length=None):
    out = Path(out_dir); (out / "thumbs").mkdir(parents=True, exist_ok=True)
    tpl = template.load(template_path)
    if length:
        tpl["length"] = length
    log("מנתח את השיר...")
    song = audio.analyze_song(song_path)
    log(f"טמפו {song['tempo']} BPM, {len(song['beats'])} ביטים")
    clips, moments = [], []
    files = sorted(p for p in Path(clips_dir).iterdir() if p.suffix.lower() in VIDEO_EXT)
    for p in files:
        log(f"מנתח קליפ {p.name}...")
        c = video.analyze_clip(p.resolve())
        ms = video.find_moments(c)
        for j, m in enumerate(ms):
            m["clip_duration"] = c["duration"]
            m["id"] = f"{p.stem}_{j}"
            th = out / "thumbs" / f"{m['id']}.jpg"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(m["peak"]), "-i", str(p),
                            "-frames:v", "1", "-vf", "scale=180:-2", str(th)])
            m["thumb"] = f"thumbs/{th.name}"
        clips.append({"path": c["path"], "name": p.name, "duration": c["duration"],
                      "width": c["width"], "height": c["height"],
                      "times": c["times"], "motion": c["motion"], "vertical": c["vertical"]})
        moments += ms
    w0, w1 = audio.best_window(song, tpl["length"])
    song["window"] = [w0, w1]
    grid = song["beats"] + [song["duration"]]
    log(f"הקטע הכי חזק בשיר: {grid[w0]:.1f}s עד {grid[w1]:.1f}s")
    proj = {"version": 1, "song": dict(song, path=str(Path(song_path).resolve())),
            "clips": clips, "moments": moments, "template": tpl}
    proj["timeline"] = planner.build_timeline(proj["song"], moments, tpl)
    save(proj, out)
    log(f"נבנה טיימליין עם {len(proj['timeline'])} חיתוכים")
    return proj


def replan(proj):
    locked = [s for s in proj["timeline"] if s.get("locked")]
    proj["timeline"] = planner.build_timeline(proj["song"], proj["moments"], proj["template"], locked)
    return proj


def save(proj, out_dir):
    Path(out_dir, "project.json").write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")


def load(out_dir):
    return json.loads(Path(out_dir, "project.json").read_text(encoding="utf-8"))
