#!/usr/bin/env python3
"""Assemble 25s 9:16 Instagram reel."""
import os, math, subprocess, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from imageio_ffmpeg import get_ffmpeg_exe

ROOT = "/home/user/Instagram-reel-content."
PROD = os.path.join(ROOT, "production")
OUT = os.path.join(PROD, "school_app_reel.mp4")
W, H, FPS = 1080, 1920, 30
DURATION = 25.0
N = int(DURATION * FPS)
FF = get_ffmpeg_exe()

REC = os.path.join(ROOT, "Video-asset/Recording 2026-09-18 232821.mp4")
HOOK = os.path.join(PROD, "avatar_hook.jpg")
CTA = os.path.join(PROD, "avatar_cta.jpg")
VO = os.path.join(PROD, "vo_full.mp3")
UI_ATT = os.path.join(PROD, "ui_attendance.jpg")
UI_FEE = os.path.join(PROD, "ui_fees.jpg")
UI_ALR = os.path.join(PROD, "ui_alerts.jpg")
UI_WEB = os.path.join(PROD, "ui_website.jpg")
UI_DASH = os.path.join(PROD, "ui_dashboard.jpg")


def load_img(path):
    im = Image.open(path).convert("RGB")
    return im


def cover(im, w=W, h=H):
    iw, ih = im.size
    s = max(w / iw, h / ih)
    nw, nh = int(iw * s) + 2, int(ih * s) + 2
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    l = (nw - w) // 2
    t = (nh - h) // 2
    return im.crop((l, t, l + w, t + h))


def kenburns(im, t, dur, zoom_from=1.0, zoom_to=1.12, pan=(0, -20)):
    base = cover(im, int(W * 1.2), int(H * 1.2))
    p = t / max(dur, 0.001)
    z = zoom_from + (zoom_to - zoom_from) * p
    bw, bh = base.size
    cw, ch = int(W / z * (bw / (W * 1.2))), int(H / z * (bh / (H * 1.2)))
    # simpler: scale then crop
    scaled = base.resize((int(bw * z), int(bh * z)), Image.Resampling.BILINEAR)
    sw, sh = scaled.size
    ox = int((sw - W) / 2 + pan[0] * p)
    oy = int((sh - H) / 2 + pan[1] * p)
    ox = max(0, min(ox, sw - W))
    oy = max(0, min(oy, sh - H))
    return scaled.crop((ox, oy, ox + W, oy + H))


def landscape_cover(frame_bgr, zoom=1.0, panx=0.0):
    """Fit landscape UI into 9:16 with blurred fill."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb)
    bg = cover(im.filter(ImageFilter.GaussianBlur(28)))
    bg = ImageEnhance.Brightness(bg).enhance(0.45)
    # letterbox UI as wide card
    iw, ih = im.size
    target_w = int(W * 0.96)
    target_h = int(target_w * ih / iw)
    ui = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
    # zoom crop on UI
    if zoom > 1.0:
        zw, zh = int(target_w / zoom), int(target_h / zoom)
        cx = int((target_w - zw) / 2 + panx)
        cy = (target_h - zh) // 2
        cx = max(0, min(cx, target_w - zw))
        ui = ui.crop((cx, cy, cx + zw, cy + zh)).resize((target_w, int(target_w * ih / iw)), Image.Resampling.LANCZOS)
        target_h = ui.size[1]
    y = (H - target_h) // 2
    y = max(180, min(y, H - target_h - 220))
    bg.paste(ui, ((W - ui.size[0]) // 2, y))
    return bg


def rec_frame(cap, t_in_source):
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    idx = int(t_in_source * fps)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    idx = max(0, min(idx, n - 1))
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, fr = cap.read()
    return fr if ok else None


def font(size, bold=True):
    cands = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for p in cands:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def overlay_label(im, text, appear=1.0):
    d = ImageDraw.Draw(im, "RGBA")
    f = font(64)
    bbox = d.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 36, 18
    x = (W - tw) // 2
    y = 140
    # pill
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    r = 28
    box = [x - pad_x, y - pad_y, x + tw + pad_x, y + th + pad_y]
    fill = (10, 18, 40, int(230 * appear))
    od.rounded_rectangle(box, radius=r, fill=fill)
    od.text((x, y), text, font=f, fill=(255, 255, 255, int(255 * appear)))
    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    return im


def overlay_cta(im):
    return overlay_label(im, "LINK IN CAPTION  ⬇", 1.0)


def phone_frame_still(path, t, dur, zoom_from=1.0, zoom_to=1.08):
    im = load_img(path)
    return kenburns(im, t, dur, zoom_from, zoom_to, pan=(0, 12))


def ease(p):
    return 0.5 - 0.5 * math.cos(math.pi * min(max(p, 0), 1))


def main():
    hook = load_img(HOOK)
    cta = load_img(CTA)
    cap = cv2.VideoCapture(REC)

    # source time mapping in the 34.8s recording
    # 0-12s website, later dashboard ~18s+
    rec_n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    rec_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    rec_dur = rec_n / rec_fps

    raw = os.path.join(PROD, "_video_raw.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    tmp_avi = os.path.join(PROD, "_tmp.avi")
    # write png pipe via ffmpeg instead
    cmd = [
        FF, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
        "-crf", "18", raw,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def scene_of(t):
        if t < 3:
            return "hook", t, 3
        if t < 6:
            return "reveal", t - 3, 3
        if t < 9:
            return "att", t - 6, 3
        if t < 12:
            return "fees", t - 9, 3
        if t < 15:
            return "alerts", t - 12, 3
        if t < 18:
            return "web", t - 15, 3
        if t < 22:
            return "scale", t - 18, 4
        return "cta", t - 22, 3

    for i in range(N):
        t = i / FPS
        name, lt, dur = scene_of(t)
        if name == "hook":
            frame = kenburns(hook, lt, dur, 1.0, 1.08, (0, -18))
        elif name == "reveal":
            fr = rec_frame(cap, 18 + lt * 1.2)
            if fr is None:
                frame = phone_frame_still(UI_DASH, lt, dur)
            else:
                z = 1.0 + 0.15 * ease(lt / dur)
                frame = landscape_cover(fr, zoom=z)
            if lt > 0.4:
                frame = overlay_label(frame, "SCHOOL APP + WEBSITE", min(1, (lt - 0.4) / 0.3))
        elif name == "att":
            # mix product dashboard attendance + ui
            fr = rec_frame(cap, 20 + lt)
            if fr is not None and lt < 1.4:
                frame = landscape_cover(fr, zoom=1.05 + 0.08 * lt)
            else:
                frame = phone_frame_still(UI_ATT, lt, dur, 1.0, 1.1)
            frame = overlay_label(frame, "ATTENDANCE  ✅", min(1, lt / 0.25))
        elif name == "fees":
            fr = rec_frame(cap, 22 + lt)
            if fr is not None and lt < 1.3:
                frame = landscape_cover(fr, zoom=1.08, panx=lt * 20)
            else:
                frame = phone_frame_still(UI_FEE, lt, dur)
            frame = overlay_label(frame, "FEES  💰", min(1, lt / 0.25))
        elif name == "alerts":
            frame = phone_frame_still(UI_ALR, lt, dur, 1.02, 1.12)
            frame = overlay_label(frame, "PARENT ALERTS  🔔", min(1, lt / 0.25))
        elif name == "web":
            fr = rec_frame(cap, 2 + lt * 3.5)
            if fr is None:
                frame = phone_frame_still(UI_WEB, lt, dur)
            else:
                frame = landscape_cover(fr, zoom=1.0 + 0.1 * lt)
            frame = overlay_label(frame, "SCHOOL WEBSITE  🌐", min(1, lt / 0.25))
        elif name == "scale":
            fr = rec_frame(cap, 24 + lt * 1.5)
            if fr is None:
                frame = phone_frame_still(UI_DASH, lt, dur, 1.0, 1.15)
            else:
                frame = landscape_cover(fr, zoom=1.0 + 0.12 * (lt / dur))
            frame = overlay_label(frame, "100  →  2000 STUDENTS", min(1, lt / 0.3))
        else:
            frame = kenburns(cta, lt, dur, 1.0, 1.06, (0, 10))
            if lt > 0.3:
                frame = overlay_cta(frame)

        arr = np.array(frame.convert("RGB"), dtype=np.uint8)
        proc.stdin.write(arr.tobytes())
        if i % 75 == 0:
            print(f"frame {i}/{N} {name}", flush=True)

    proc.stdin.close()
    proc.wait()
    cap.release()
    print("video written", raw)

    # speed VO to ~25s and mix
    vo_fit = os.path.join(PROD, "vo_25.mp3")
    # 30.48 -> 25 : atempo 1.22
    subprocess.check_call([
        FF, "-y", "-i", VO, "-filter:a", "atempo=1.22,volume=2.2",
        "-vn", vo_fit
    ])
    # simple bed: low filtered noise-ish tone via sine stack
    bed = os.path.join(PROD, "bed.wav")
    subprocess.check_call([
        FF, "-y", "-f", "lavfi", "-i",
        "sine=frequency=220:sample_rate=44100:duration=25,volume=0.04",
        "-f", "lavfi", "-i",
        "sine=frequency=330:sample_rate=44100:duration=25,volume=0.03",
        "-filter_complex", "[0][1]amix=inputs=2:duration=first,highpass=f=80",
        bed
    ])
    final = OUT
    subprocess.check_call([
        FF, "-y", "-i", raw, "-i", vo_fit, "-i", bed,
        "-filter_complex",
        "[1:a]aformat=sample_rates=44100:channel_layouts=stereo[vo];"
        "[2:a]volume=0.25[bd];"
        "[vo][bd]amix=inputs=2:duration=first:dropout_transition=0[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "17",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        final,
    ])
    print("DONE", final, os.path.getsize(final))


if __name__ == "__main__":
    main()
