import subprocess
import json

for name in ['source_edit_1.mp4', 'source_edit_2.mp4', 'trailer1.mp4']:
    path = f'temp_raw2/{name}'
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', '-show_format', path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(res.stdout)
    v = next(s for s in data['streams'] if s['codec_type'] == 'video')
    print(f"{name}: {v['width']}x{v['height']}, fps: {v.get('r_frame_rate')}, duration: {data['format']['duration']}s")
