"""רנדר סופי ב-ffmpeg: 9:16, חיתוך מדויק לפריים, האטה, זום/פלאש בדרופ, והשיר מעל."""
import subprocess
import tempfile
from pathlib import Path


def render(project, out_path, log=print):
    tpl = project["template"]
    W, H, FPS = tpl["width"], tpl["height"], tpl["fps"]
    tmp = Path(tempfile.mkdtemp(prefix="beatcut_"))
    parts = []
    for k, s in enumerate(project["timeline"]):
        f0, f1 = round(s["start"] * FPS), round(s["end"] * FPS)
        frames = max(1, f1 - f0)
        speed = s.get("speed", 1.0)
        z = s.get("fx", {}).get("zoom", 1.0)
        vf = [f"setpts=PTS/{speed}", f"fps={FPS}",
              f"scale={W}:{H}:force_original_aspect_ratio=increase", f"crop={W}:{H}"]
        if z and z > 1.001:
            # "פאנץ'" זום שיורד מהר בחצי השנייה הראשונה
            vf.append(f"scale=iw*({z}-({z}-1)*min(t/0.4\\,1)):-2:eval=frame,crop={W}:{H}")
        if s.get("fx", {}).get("flash"):
            vf.append("eq=brightness='0.6*max(0\\,1-t/0.15)':eval=frame")
        vf += ["setsar=1", "format=yuv420p"]
        part = tmp / f"p{k:04d}.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(s["in"]), "-i", s["clip"],
               "-vf", ",".join(vf), "-frames:v", str(frames), "-an",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), str(part)]
        subprocess.run(cmd, check=True)
        parts.append(part)
        log(f"segment {k + 1}/{len(project['timeline'])}")
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    end = project["timeline"][-1]["end"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
           "-i", project["song"]["path"], "-map", "0:v", "-map", "1:a", "-t", str(end),
           "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out_path)]
    subprocess.run(cmd, check=True)
    return str(out_path)
