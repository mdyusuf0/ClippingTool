import os
import subprocess

OUTPUT_DIR = r"C:\Users\yusuf\Desktop"
VINE_BOOM = "temp_audio/vine_boom.wav"
BRUH_SOUND = "temp_audio/bruh.wav"

# --- 1. RENDER XQC REEL ---
xqc_out = os.path.join(OUTPUT_DIR, "GTA6_Glitch_xQc_RadioDemon_Reel.mp4")
xqc_ass = "temp_subs2/xqc_glitch.ass".replace("\\", "/")

# Video Filter: Stack Top (xQc Webcam) and Bottom (GTA 6 Gameplay) + Subtitles
xqc_vf = (
    "[0:v]crop=368:202:0:542,scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[cam];"
    "[0:v]crop=960:854:480:226,scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[game];"
    f"[cam][game]vstack,ass='{xqc_ass}'[v]"
)

# Audio Filter: Original audio + Vine Boom at 4s + Bruh at 18.5s
xqc_af = (
    "[1:a]adelay=4000|4000,volume=1.4[sfx1];"
    "[2:a]adelay=18500|18500,volume=1.5[sfx2];"
    "[0:a]volume=1.4[voice];"
    "[voice][sfx1][sfx2]amix=inputs=3:duration=first:dropout_transition=2,loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
)

xqc_cmd = [
    "ffmpeg", "-y",
    "-ss", "31.0",
    "-i", "temp_raw2/xqc_gta6.mp4",
    "-i", VINE_BOOM,
    "-i", BRUH_SOUND,
    "-filter_complex", f"{xqc_vf};{xqc_af}",
    "-map", "[v]",
    "-map", "[aout]",
    "-t", "24.0",
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-r", "30",
    "-c:a", "aac",
    "-b:a", "192k",
    xqc_out
]

print("---> Rendering xQc Glitch Reel...")
res1 = subprocess.run(xqc_cmd, capture_output=True, text=True)
if res1.returncode != 0:
    print("Error xQc Reel:", res1.stderr)
else:
    sz = os.path.getsize(xqc_out) / (1024 * 1024)
    print(f"Successfully created: {xqc_out} ({sz:.2f} MB)")


# --- 2. RENDER SPEED REEL ---
speed_out = os.path.join(OUTPUT_DIR, "GTA6_Glitch_Speed_KFC_Keanu_Reel.mp4")
speed_ass = "temp_subs2/speed_kfc.ass".replace("\\", "/")

# Video Filter: Stack Top (Speed Facecam) and Bottom (GTA 6 KFC Character) + Subtitles
speed_vf = (
    "[0:v]crop=700:490:0:560,scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[cam];"
    "[0:v]crop=1000:720:460:120,scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[game];"
    f"[cam][game]vstack,ass='{speed_ass}'[v]"
)

# Audio Filter: Original voice + Vine Boom at 8.5s + Bruh at 17.5s
speed_af = (
    "[1:a]adelay=8500|8500,volume=1.4[sfx1];"
    "[2:a]adelay=17500|17500,volume=1.5[sfx2];"
    "[0:a]volume=1.3[voice];"
    "[voice][sfx1][sfx2]amix=inputs=3:duration=first:dropout_transition=2,loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
)

speed_cmd = [
    "ffmpeg", "-y",
    "-ss", "117.0",
    "-i", "temp_raw2/speed_reacts.mp4",
    "-i", VINE_BOOM,
    "-i", BRUH_SOUND,
    "-filter_complex", f"{speed_vf};{speed_af}",
    "-map", "[v]",
    "-map", "[aout]",
    "-t", "22.0",
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-r", "30",
    "-c:a", "aac",
    "-b:a", "192k",
    speed_out
]

print("\n---> Rendering Speed Glitch Reel...")
res2 = subprocess.run(speed_cmd, capture_output=True, text=True)
if res2.returncode != 0:
    print("Error Speed Reel:", res2.stderr)
else:
    sz = os.path.getsize(speed_out) / (1024 * 1024)
    print(f"Successfully created: {speed_out} ({sz:.2f} MB)")

print("\nBoth creator glitch reels rendered successfully!")
