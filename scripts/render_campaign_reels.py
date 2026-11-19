"""
render_campaign_reels.py
========================
Render 4 distinct GTA 6 viral reels for the PASSIVE / PLACEMENTS 'Tokyo Girl' campaign:
- 2 from IShowSpeed (Hype / Waiting for GTA 6 + Emotional Lucia Custody scene)
- 2 from CarryMinati (Lucia Police Arrest / Sacrifice + Late Night Vice City Boat Cruise)

Audio: 'Tokyo Girl' by Passive (Official Audio, -14 LUFS, video speech muted).
Video: 1080x1920 (9:16 vertical), two-stage cinematic bokeh blur, ASS styled text hooks.
Saved to: Desktop
"""

from __future__ import annotations

import subprocess
from pathlib import Path

DESKTOP = Path("C:/Users/yusuf/Desktop")
AUDIO_TRACK = Path("temp_audio/tokyo_girl.wav")

REELS = [
    {
        "raw": Path("temp_raw/speed_raw_1.mp4"),
        "out": DESKTOP / "GTA6_TokyoGirl_Speed_Hype_Reel.mp4",
        "title1": "WAITING 12 YEARS FOR GTA 6...",
        "sub1": "Got us like this 😭💔 (2026 feels so far away)",
        "title2": "Tell me we are not the only ones counting down every second... 🥺",
        "sub2": "GTA 6 • Vice City • 2026",
        "ass": Path("temp_reel1.ass"),
    },
    {
        "raw": Path("temp_raw/speed_raw_2.mp4"),
        "out": DESKTOP / "GTA6_TokyoGirl_Speed_Story_Reel.mp4",
        "title1": "LUCIA'S STORY IS GOING TO BREAK US 💔",
        "sub1": "If they let me out... do I get custody of my son? 🥺",
        "title2": "GTA 6 story is going to hit way too deep... 😭",
        "sub2": "Lucia & Jason • Partners In Crime",
        "ass": Path("temp_reel2.ass"),
    },
    {
        "raw": Path("temp_raw/carry_raw_1.mp4"),
        "out": DESKTOP / "GTA6_TokyoGirl_Carry_Arrest_Reel.mp4",
        "title1": "SHE TOOK THE BLAME SO HE COULD GET AWAY 💔",
        "sub1": "The only way out is together... 🥺",
        "title2": "Trust is everything in Vice City... 🥀",
        "sub2": "Vice City 2026 • Real Ones Know",
        "ass": Path("temp_reel3.ass"),
    },
    {
        "raw": Path("temp_raw/carry_raw_2.mp4"),
        "out": DESKTOP / "GTA6_TokyoGirl_Carry_ViceCity_Reel.mp4",
        "title1": "LATE NIGHT CRUISES IN VICE CITY 🌅🌴",
        "sub1": "We really waited a whole decade for this feeling... 🥺",
        "title2": "Can't believe we are finally going back in 2026 💜",
        "sub2": "Vice City • Sunset Ocean Views",
        "ass": Path("temp_reel4.ass"),
    },
]

AUDIO_FILTER = "loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:ss=0:d=0.3,afade=t=out:st=24.2:d=0.6"


def create_ass_file(path: Path, title1: str, sub1: str, title2: str, sub2: str) -> None:
    content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TitleHook,Arial,56,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,3,2,60,60,1400,1
Style: SubHook,Arial,44,&H008571FB,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,1310,1
Style: BottomCaption,Arial,48,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,60,60,330,1
Style: BottomSub,Arial,38,&H0000D7FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,60,60,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.50,0:00:12.00,TitleHook,,0,0,0,,{title1}
Dialogue: 0,0:00:01.80,0:00:12.00,SubHook,,0,0,0,,{sub1}
Dialogue: 0,0:00:12.50,0:00:24.50,BottomCaption,,0,0,0,,{title2}
Dialogue: 0,0:00:14.00,0:00:24.50,BottomSub,,0,0,0,,{sub2}
"""
    path.write_text(content, encoding="utf-8")


def main() -> None:
    DESKTOP.mkdir(parents=True, exist_ok=True)

    for i, r in enumerate(REELS, 1):
        print(f"\n--- [Reel {i}/4] Rendering: {r['out'].name} ---")
        create_ass_file(r["ass"], r["title1"], r["sub1"], r["title2"], r["sub2"])

        ass_str = str(r["ass"]).replace("\\", "/")
        vf = (
            "[0:v]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,boxblur=8:1,scale=1080:1920[bg];"
            "[0:v]scale=1080:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
            f"[base]ass='{ass_str}'[v]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-nostdin",
            "-threads", "0",
            "-i", str(r["raw"]),
            "-i", str(AUDIO_TRACK),
            "-filter_complex", vf,
            "-map", "[v]",
            "-map", "1:a",
            "-af", AUDIO_FILTER,
            "-c:v", "libx264",
            "-crf", "20",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", "25",
            "-movflags", "+faststart",
            str(r["out"]),
        ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Error on Reel {i}:\n{res.stderr[-500:]}")
        else:
            size_mb = r["out"].stat().st_size / (1024 * 1024)
            print(f"SUCCESS! Created {r['out'].name} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
