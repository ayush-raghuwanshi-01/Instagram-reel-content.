#!/usr/bin/env python3
"""Viral 25s 9:16 reel: viseme lip-sync, snap zooms, punchy bed."""
import os, math, subprocess, struct, wave, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops
from imageio_ffmpeg import get_ffmpeg_exe

ROOT = "/home/user/Instagram-reel-content."
PROD = os.path.join(ROOT, "production")
W, H, FPS = 1080, 1920, 30
DURATION = 25.0
N = int(DURATION * FPS)
FF = get_ffmpeg_exe()
REC = os.path.join(ROOT, "Video-asset/Recording 2026-09-18 232821.mp4")
VO_SRC = os.path.join(PROD, "vo_full.mp3")
OUT = os.path.join(PROD, "INSTAGRAM_REEL_FINAL.mp4")


def ff(*args):
    subprocess.check_call([FF, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def load(p):
    return Image.open(p).convert("RGB")


def cover(im, w=W, h=H):
    iw, ih = im.size
    s = max(w / iw, h / ih)
    nw, nh = int(iw * s) + 2, int(ih * s) + 2
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    l, t = (nw - w) // 2, (nh - h) // 2
    return im.crop((l, t, l + w, t + h))


def zoom_crop(im, z, panx=0, pany=0):
    """z>=1. Center crop after scale."""
    base = cover(im, W, H)
    if z <= 1.001:
        return base
    nw, nh = int(W * z), int(H * z)
    big = base.resize((nw, nh), Image.Resampling.BILINEAR)
    ox = int((nw - W) / 2 + panx)
    oy = int((nh - H) / 2 + pany)
    ox = max(0, min(ox, nw - W))
    oy = max(0, min(oy, nh - H))
    return big.crop((ox, oy, ox + W, oy + H))


def snap_zoom(t_in_scene, base_z=1.02):
    """Punch: 1.22 -> 1.04 in first 6 frames of a scene."""
    punch = 6 / FPS
    if t_in_scene < punch:
        p = t_in_scene / punch
        return 1.22 - 0.18 * (1 - (1 - p) ** 2)
    return base_z + 0.06 * min(1, t_in_scene / 2.5)


def font(size):
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def draw_caption(im, lines, appear=1.0, y=1480):
    if appear <= 0:
        return im
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    f = font(52)
    max_w = 0
    heights = []
    for line in lines:
        bb = d.textbbox((0, 0), line, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        max_w = max(max_w, tw)
        heights.append(th)
    pad_x, pad_y, gap = 28, 16, 8
    total_h = sum(heights) + gap * (len(lines) - 1)
    box_w = max_w + pad_x * 2
    box_h = total_h + pad_y * 2
    x0 = (W - box_w) // 2
    y0 = y
    alpha = int(230 * appear)
    d.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], 22, fill=(8, 12, 28, alpha))
    cy = y0 + pad_y
    for line, th in zip(lines, heights):
        bb = d.textbbox((0, 0), line, font=f)
        tw = bb[2] - bb[0]
        d.text(((W - tw) // 2, cy), line, font=f, fill=(255, 255, 255, int(255 * appear)))
        cy += th + gap
    return Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")


def stamp(im, text, y=120, appear=1.0, color=(255, 230, 40)):
    if appear <= 0:
        return im
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    f = font(58)
    bb = d.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x = (W - tw) // 2
    d.rounded_rectangle([x - 28, y - 12, x + tw + 28, y + th + 16], 26, fill=(10, 16, 36, int(235 * appear)))
    d.text((x, y), text, font=f, fill=(*color, int(255 * appear)))
    return Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")


def landscape_card(frame_bgr, z=1.0):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb)
    bg = cover(im.filter(ImageFilter.GaussianBlur(36)))
    bg = ImageEnhance.Brightness(bg).enhance(0.35)
    iw, ih = im.size
    tw = int(W * 0.94)
    th = int(tw * ih / iw)
    ui = im.resize((tw, th), Image.Resampling.LANCZOS)
    if z > 1:
        zw, zh = int(tw / z), int(th / z)
        cx, cy = (tw - zw) // 2, (th - zh) // 2
        ui = ui.crop((cx, cy, cx + zw, cy + zh)).resize((tw, th), Image.Resampling.BILINEAR)
    y = (H - th) // 2 - 40
    y = max(200, min(y, H - th - 280))
    # phone-ish shadow
    shadow = Image.new("RGB", (tw, th), (0, 0, 0))
    bg.paste(shadow, ((W - tw) // 2 + 8, y + 10))
    bg.paste(ui, ((W - tw) // 2, y))
    return bg


def rec_frame(cap, t):
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    idx = int(max(0, min(t * fps, n - 2)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, fr = cap.read()
    return fr if ok else None


def envelope(wav_path, fps=FPS, n=N):
    w = wave.open(wav_path)
    sr = w.getframerate()
    ch = w.getnchannels()
    sw = w.getsampwidth()
    raw = w.readframes(w.getnframes())
    w.close()
    if sw == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    else:
        data = np.frombuffer(raw, dtype=np.int8).astype(np.float32)
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    data = np.abs(data)
    hop = sr / fps
    env = []
    for i in range(n):
        a = int(i * hop)
        b = int((i + 1) * hop)
        env.append(float(data[a:b].mean()) if b > a else 0.0)
    env = np.array(env)
    env = env / (np.percentile(env, 92) + 1e-6)
    env = np.clip(env, 0, 1)
    # smooth
    k = 3
    kernel = np.ones(k) / k
    env = np.convolve(env, kernel, mode="same")
    return env


def viseme_blend(closed, mid, opened, e):
    if e < 0.22:
        a = e / 0.22
        return Image.blend(closed, mid, a)
    a = min(1.0, (e - 0.22) / 0.55)
    return Image.blend(mid, opened, a)


def make_bed(path):
    # kick + hat-ish reel bed using sine bursts (not a licensed track)
    ff(
        "-y",
        "-f", "lavfi", "-i", "sine=frequency=70:sample_rate=44100:duration=25",
        "-f", "lavfi", "-i", "sine=frequency=180:sample_rate=44100:duration=25",
        "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=44100:duration=25",
        "-filter_complex",
        # gate into 4-on-floor-ish: volume tremolo
        "[0]tremolo=f=2:d=0.9,volume=0.35[k];"
        "[1]tremolo=f=4:d=0.7,highpass=f=120,volume=0.12[b];"
        "[2]tremolo=f=8:d=0.85,highpass=f=600,volume=0.05[h];"
        "[k][b][h]amix=inputs=3:duration=first,alimiter=limit=0.35",
        path,
    )


def main():
    vo25 = os.path.join(PROD, "vo_25.wav")
    ff("-y", "-i", VO_SRC, "-filter:a", "atempo=1.22,volume=2.4", "-ar", "24000", "-ac", "1", vo25)
    env = envelope(vo25)

    hook_c = cover(load(os.path.join(PROD, "avatar_hook_closed.jpg")))
    hook_m = cover(load(os.path.join(PROD, "avatar_hook_mid.jpg")))
    hook_o = cover(load(os.path.join(PROD, "avatar_hook_open.jpg")))
    cta_c = cover(load(os.path.join(PROD, "avatar_cta_closed.jpg")))
    cta_o = cover(load(os.path.join(PROD, "avatar_cta_open.jpg")))
    ui_att = load(os.path.join(PROD, "ui_attendance.jpg"))
    ui_fee = load(os.path.join(PROD, "ui_fees.jpg"))
    ui_alr = load(os.path.join(PROD, "ui_alerts.jpg"))
    ui_web = load(os.path.join(PROD, "ui_website.jpg"))
    ui_dash = load(os.path.join(PROD, "ui_dashboard.jpg"))

    cap = cv2.VideoCapture(REC)
    raw = os.path.join(PROD, "_v2_raw.mp4")
    proc = subprocess.Popen(
        [
            FF, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "17", raw,
        ],
        stdin=subprocess.PIPE,
    )

    def scene(t):
        cuts = [
            (3, "hook"),
            (6, "reveal"),
            (9, "att"),
            (12, "fees"),
            (15, "alerts"),
            (18, "web"),
            (22, "scale"),
            (25, "cta"),
        ]
        start = 0
        for end, name in cuts:
            if t < end:
                return name, t - start, end - start
            start = end
        return "cta", 0, 3

    captions = {
        "hook": (["School mein yeh nahi hai?"], 1320),
        "reveal": (["Poora school", "DIGITAL"], 1320),
        "att": (["Attendance —", "ek tap"], 1320),
        "fees": (["Fees + payments", "transparent"], 1320),
        "alerts": (["Parents ko", "seedha alert"], 1320),
        "web": (["School ki", "apni website"], 1320),
        "scale": (["100 ya 2000", "same app"], 1320),
        "cta": (["Demo? Link caption mein"], 1380),
    }
    stamps = {
        "reveal": "SCHOOL APP + WEB",
        "att": "ATTENDANCE  ✅",
        "fees": "FEES  💰",
        "alerts": "PARENT ALERTS  🔔",
        "web": "WEBSITE  🌐",
        "scale": "100 → 2000 STUDENTS",
        "cta": "LINK IN CAPTION  ⬇",
    }

    for i in range(N):
        t = i / FPS
        name, lt, dur = scene(t)
        e = float(env[i]) if i < len(env) else 0
        z = snap_zoom(lt)

        if name == "hook":
            face = viseme_blend(hook_c, hook_m, hook_o, e)
            frame = zoom_crop(face, z, pany=-int(8 * lt))
        elif name == "cta":
            face = Image.blend(cta_c, cta_o, min(1, e * 1.3))
            frame = zoom_crop(face, z, pany=int(6 * lt))
        elif name == "reveal":
            fr = rec_frame(cap, 18.2 + lt * 1.4)
            frame = landscape_card(fr, 1.0 + 0.12 * (lt / dur)) if fr is not None else zoom_crop(ui_dash, z)
        elif name == "att":
            if lt < 1.2:
                fr = rec_frame(cap, 20.5 + lt)
                frame = landscape_card(fr, 1.05 + 0.1 * lt) if fr is not None else zoom_crop(ui_att, z)
            else:
                frame = zoom_crop(ui_att, z)
        elif name == "fees":
            if lt < 1.2:
                fr = rec_frame(cap, 22.5 + lt)
                frame = landscape_card(fr, 1.08) if fr is not None else zoom_crop(ui_fee, z)
            else:
                frame = zoom_crop(ui_fee, z)
        elif name == "alerts":
            frame = zoom_crop(ui_alr, z)
        elif name == "web":
            fr = rec_frame(cap, 1.5 + lt * 3.2)
            frame = landscape_card(fr, 1.0 + 0.15 * (lt / dur)) if fr is not None else zoom_crop(ui_web, z)
        else:
            fr = rec_frame(cap, 25 + lt)
            frame = landscape_card(fr, 1.0 + 0.18 * (lt / dur)) if fr is not None else zoom_crop(ui_dash, z)

        # white flash on cut (first 2 frames)
        if lt < 2 / FPS:
            flash = Image.new("RGB", (W, H), (255, 255, 255))
            frame = Image.blend(frame, flash, 0.35)

        appear = min(1.0, lt / 0.18)
        if name in stamps:
            frame = stamp(frame, stamps[name], appear=appear)
        lines, cy = captions[name]
        frame = draw_caption(frame, lines, appear=appear, y=cy)

        proc.stdin.write(np.array(frame.convert("RGB"), dtype=np.uint8).tobytes())
        if i % 75 == 0:
            print(f"{i}/{N} {name} e={e:.2f} z={z:.2f}", flush=True)

    proc.stdin.close()
    proc.wait()
    cap.release()

    bed = os.path.join(PROD, "bed_v2.wav")
    make_bed(bed)
    vo_mp3 = os.path.join(PROD, "vo_25.mp3")
    ff("-y", "-i", vo25, vo_mp3)

    ff(
        "-y", "-i", raw, "-i", vo_mp3, "-i", bed,
        "-filter_complex",
        "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=2.6[vo];"
        "[2:a]volume=0.22,highpass=f=60[bd];"
        # bed silent first 2.8s (hook dry)
        "[bd]volume=enable='lt(t,2.8)':volume=0[bd2];"
        "[vo][bd2]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.95[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "16",
        "-profile:v", "high", "-level", "4.1",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-shortest", "-movflags", "+faststart",
        "-metadata", "title=School Management App Reel",
        OUT,
    )
    print("DONE", OUT, os.path.getsize(OUT))


if __name__ == "__main__":
    main()
