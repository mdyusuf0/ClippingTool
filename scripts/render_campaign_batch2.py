import os
import subprocess
import sys

AUDIO_PATH = "temp_audio/tokyo_girl.wav"
OUTPUT_DIR = r"C:\Users\yusuf\Desktop"
TEMP_SUBS = "temp_subs2"

os.makedirs(TEMP_SUBS, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_ass(filename, lines):
    header = """[Script Info]
Title: Tokyo Girl Campaign Reel
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: MainHook,Arial,52,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3.5,2,2,40,40,320,1
Style: SubHook,Arial,48,&H008571FB,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3.5,2,2,40,40,240,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for start, end, style, text in lines:
        events.append(f"Dialogue: 0,{start},{end},{style},,0,0,0,,{text}")
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")

reels_config = [
    {
        "name": "GTA6_TokyoGirl_Landscape_Sunset_Reel.mp4",
        "source": "temp_raw2/trailer1.mp4",
        "ss": 8.0,
        "subs_file": os.path.join(TEMP_SUBS, "reel5.ass"),
        "lines": [
            ("0:00:00.80", "0:00:11.80", "MainHook", "some cities look like heaven from far away..."),
            ("0:00:12.30", "0:00:24.50", "SubHook", "until you realize how lonely paradise can be.")
        ]
    },
    {
        "name": "GTA6_TokyoGirl_Lucia_Prison_Reel.mp4",
        "source": "temp_raw2/scenepack_twixtor.mp4",
        "ss": 0.0,
        "subs_file": os.path.join(TEMP_SUBS, "reel6.ass"),
        "lines": [
            ("0:00:00.80", "0:00:11.80", "MainHook", "she thought love was worth risking everything."),
            ("0:00:12.30", "0:00:24.50", "SubHook", "now she counts the sunsets through a fence.")
        ]
    },
    {
        "name": "GTA6_TokyoGirl_JasonLucia_Trust_Reel.mp4",
        "source": "temp_raw2/trailer1.mp4",
        "ss": 62.0,
        "subs_file": os.path.join(TEMP_SUBS, "reel7.ass"),
        "lines": [
            ("0:00:00.80", "0:00:11.80", "MainHook", "we said it was us against the whole world..."),
            ("0:00:12.30", "0:00:24.50", "SubHook", "we just forgot the world always wins.")
        ]
    },
    {
        "name": "GTA6_TokyoGirl_ViceCity_NeonNights_Reel.mp4",
        "source": "temp_raw2/scenepack_twixtor.mp4",
        "ss": 7.0,
        "subs_file": os.path.join(TEMP_SUBS, "reel8.ass"),
        "lines": [
            ("0:00:00.80", "0:00:11.80", "MainHook", "surrounded by a million lights at 3 AM..."),
            ("0:00:12.30", "0:00:24.50", "SubHook", "and still feeling completely invisible.")
        ]
    }
]

print("Rendering 4 new Campaign Reels...")

for item in reels_config:
    create_ass(item["subs_file"], item["lines"])
    out_path = os.path.join(OUTPUT_DIR, item["name"])
    ass_escaped = item["subs_file"].replace("\\", "/").replace(":", "\\:")
    
    filter_complex = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,ass='{ass_escaped}'[v]"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(item["ss"]),
        "-i", item["source"],
        "-i", AUDIO_PATH,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "1:a",
        "-t", "25.0",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "192k",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:ss=0:d=0.3,afade=t=out:st=24.2:d=0.6",
        out_path
    ]
    
    print(f"\n---> Rendering: {item['name']}...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error rendering {item['name']}:\n{res.stderr}")
    else:
        size_mb = os.path.getsize(out_path) / (1024 * 1024)
        print(f"Successfully created {item['name']} ({size_mb:.2f} MB)")

print("\nAll 4 reels rendered successfully!")
