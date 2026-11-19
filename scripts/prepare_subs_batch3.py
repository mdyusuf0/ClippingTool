import os
import subprocess

OUTPUT_DIR = r"C:\Users\yusuf\Desktop"
TEMP_SUBS = "temp_subs2"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_SUBS, exist_ok=True)

# 1. Generate Subtitle for xQc
xqc_ass_path = os.path.join(TEMP_SUBS, "xqc_glitch.ass")
xqc_ass_content = """[Script Info]
Title: xQc GTA 6 Radio Glitch Reel
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CaptionText,Arial,56,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,4.0,2,2,40,40,240,1
Style: HighlightYellow,Arial,60,&H0000FFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,4.5,2,2,40,40,240,1
Style: HighlightRed,Arial,62,&H000000FF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,5.0,2,2,40,40,240,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.50,0:00:03.20,CaptionText,,0,0,0,,Radio: "No son! {\\c&H0000FFFF&}LOOK AWAY!{\\r}"
Dialogue: 0,0:00:03.50,0:00:07.50,HighlightRed,,0,0,0,,⚠️ [RADIO CORRUPTED] WHAT HAPPENED?!
Dialogue: 0,0:00:07.80,0:00:13.80,HighlightYellow,,0,0,0,,"WHAT HAPPENED?! WHY DID I GET SO DRUNK?!"
Dialogue: 0,0:00:14.20,0:00:17.50,CaptionText,,0,0,0,,xQc: "WHAT THE F***..."
Dialogue: 0,0:00:17.80,0:00:23.50,HighlightRed,,0,0,0,,"...IS HAPPENING WITH THIS GAME?!"
"""

with open(xqc_ass_path, "w", encoding="utf-8") as f:
    f.write(xqc_ass_content)

# 2. Generate Subtitle for Speed
speed_ass_path = os.path.join(TEMP_SUBS, "speed_kfc.ass")
speed_ass_content = """[Script Info]
Title: Speed GTA 6 KFC Glitch Reel
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CaptionText,Arial,56,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,4.0,2,2,40,40,240,1
Style: HighlightYellow,Arial,60,&H0000FFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,4.5,2,2,40,40,240,1
Style: HighlightCyan,Arial,62,&H00FFFF00,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,5.0,2,2,40,40,240,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.50,0:00:04.20,HighlightYellow,,0,0,0,,Speed: "WAIT... THAT'S KFC?!"
Dialogue: 0,0:00:04.50,0:00:08.20,CaptionText,,0,0,0,,"Look, that's Jason... WHO IS THAT? Tom Cruise?!"
Dialogue: 0,0:00:08.50,0:00:12.80,HighlightCyan,,0,0,0,,"NO! THAT'S KEANU REEVES! 😭"
Dialogue: 0,0:00:13.20,0:00:17.20,HighlightYellow,,0,0,0,,"BRO THEY GOT KFC IN GTA 6?!"
Dialogue: 0,0:00:17.50,0:00:21.50,CaptionText,,0,0,0,,"ABOUT TO BE EATING CHICKEN IN THE GAME?!"
"""

with open(speed_ass_path, "w", encoding="utf-8") as f:
    f.write(speed_ass_content)

print("Subtitles generated!")
