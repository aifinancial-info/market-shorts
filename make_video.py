#!/usr/bin/env python3
"""米国市況 AIナビゲーター ショート動画ジェネレーター (1080x1920, 30fps)
使い方: python3 make_video.py data.json out.mp4
"""
import json, math, os, random, subprocess, sys, wave
import numpy as np
import pyopenjtalk
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, SR = 1080, 1920, 30, 48000
FD = "/usr/share/fonts/opentype/noto/"
def F(w, s): return ImageFont.truetype(FD + f"NotoSansCJK-{w}.ttc", s, index=0)
def FM(s): return ImageFont.truetype(FD + "NotoSansCJK-Bold.ttc", s, index=5)  # mono

CY = (0, 229, 255); CY_D = (0, 90, 110); WHITE = (235, 250, 255)
UP = (255, 77, 109); DN = (64, 160, 255); FLAT = (170, 185, 195); AMB = (255, 196, 0)
BG0 = (3, 8, 18); BG1 = (6, 22, 40)

ORDER = ["intro", "headline", "indices", "rates_fx", "commodities", "analysis", "outro"]
TAGS = {"intro": "SYSTEM BOOT", "headline": "SUMMARY", "indices": "EQUITY INDEX",
        "rates_fx": "BOND / FX", "commodities": "COMMODITY / CRYPTO",
        "analysis": "AI ANALYSIS", "outro": "NEXT EVENT"}

def ease(x): x = max(0, min(1, x)); return 1 - (1 - x) ** 3

# ---------------- audio ----------------
def synth(text, path, speed=1.3):
    x, sr = pyopenjtalk.tts(text, speed=speed, half_tone=-0.5)
    x = x.astype(np.int16)
    raw = path + ".raw.wav"
    with wave.open(raw, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(x.tobytes())
    # ややデジタルな質感（ハイパス＋短いエコー＋軽いコーラス）
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
                    "highpass=f=110,aecho=0.8:0.6:18|36:0.22|0.12,chorus=0.7:0.9:40:0.3:0.2:2,"
                    "equalizer=f=3000:t=q:w=1:g=3,loudnorm=I=-16:TP=-1.5,aresample=48000",
                    "-ac", "1", path], check=True)
    os.remove(raw)
    with wave.open(path) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a

def bgm(n, marks):
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    for f, g in [(55, .22), (82.4, .12), (110, .10), (164.8, .05), (220, .03)]:
        out += g * np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 0.07 * t)) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.11 * t + f))
    beat = 60 / 96
    for k in range(int(n / SR / beat)):  # 低いパルス
        s = int(k * beat * SR); L = int(0.25 * SR)
        if s + L > n: break
        e = np.exp(-np.arange(L) / (0.05 * SR))
        out[s:s + L] += 0.35 * e * np.sin(2 * np.pi * 48 * np.arange(L) / SR)
        if k % 2 == 1:
            L2 = int(0.03 * SR); out[s:s + L2] += 0.04 * np.random.randn(L2) * np.exp(-np.arange(L2) / 200)
    for m in marks:  # 場面転換のデータ音
        s = int(m * SR)
        for j, f in enumerate([1760, 2349, 2637]):
            ss = s + int(j * 0.06 * SR); L = int(0.05 * SR)
            if ss + L < n: out[ss:ss + L] += 0.12 * np.sin(2 * np.pi * f * np.arange(L) / SR) * np.hanning(L)
        L = int(0.4 * SR)
        if s + L < n: out[s:s + L] += 0.05 * np.random.randn(L) * np.hanning(L)[::-1] ** 3
    return out / (np.abs(out).max() + 1e-9) * 0.16

# ---------------- visuals ----------------
def make_bg():
    bg = Image.new("RGB", (W, H), BG0)
    arr = np.zeros((H, W, 3), np.float32)
    yy = np.linspace(0, 1, H)[:, None]; xx = np.linspace(-1, 1, W)[None, :]
    v = np.clip(1 - np.sqrt(xx ** 2 * 0.8 + (yy - 0.22) ** 2 * 2.5), 0, 1)
    for c in range(3): arr[:, :, c] = BG0[c] + (BG1[c] - BG0[c]) * (0.4 + 0.6 * v)
    bg = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(bg)
    for x in range(0, W, 60): d.line([(x, 0), (x, H)], fill=(10, 34, 52), width=1)
    for y in range(0, H, 60): d.line([(0, y), (W, y)], fill=(10, 34, 52), width=1)
    for y in range(0, H, 4): d.line([(0, y), (W, y)], fill=(2, 6, 12), width=1)
    return bg

PARTS = [(random.random() * W, random.random() * H, random.uniform(.3, 1.5), random.randint(1, 3)) for _ in range(70)]
RINGS = [(150, 3, 0.6, 250), (175, 2, -0.35, 120), (200, 4, 0.18, 60), (228, 1, -0.9, 300)]

def avatar(amp, t, big):
    S = 560; L = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(L); c = S // 2
    sc = 1.0 if big else 0.72
    for r, wdt, sp, arc in RINGS:
        r = r * sc; a0 = (t * sp * 60) % 360
        for k in range(3):
            s = a0 + k * 120
            d.arc([c - r, c - r, c + r, c + r], s, s + arc / 3, fill=CY + (200,), width=wdt)
    # 六角形コア
    R = 105 * sc * (1 + 0.12 * amp)
    pts = [(c + R * math.cos(math.radians(60 * i + 30 + t * 8)), c + R * math.sin(math.radians(60 * i + 30 + t * 8))) for i in range(6)]
    d.polygon(pts, outline=CY + (255,), fill=(0, 60, 80, 110))
    pts2 = [(c + R * .72 * math.cos(math.radians(60 * i - t * 15)), c + R * .72 * math.sin(math.radians(60 * i - t * 15))) for i in range(6)]
    d.polygon(pts2, outline=CY + (150,))
    # 音声波形（口）
    n = 34; bw = 2 * R * 0.8 / n
    for i in range(n):
        x = c - R * 0.8 + i * bw
        h = 4 + amp * 70 * sc * abs(math.sin(i * 0.9 + t * 13)) * math.exp(-((i - n / 2) / (n / 3)) ** 2)
        d.rectangle([x, c - h, x + bw * 0.55, c + h], fill=WHITE + (235,))
    glow = L.filter(ImageFilter.GaussianBlur(14))
    out = Image.alpha_composite(glow, glow); out = Image.alpha_composite(out, L)
    return out

def text_c(d, xy, s, f, fill, anchor="mm", glow=None):
    if glow: d.text(xy, s, font=f, fill=glow, anchor=anchor, stroke_width=6, stroke_fill=glow)
    d.text(xy, s, font=f, fill=fill, anchor=anchor)

def frame_box(d, box, col=CY, a=1.0):
    x0, y0, x1, y1 = box; k = 26
    cc = tuple(int(v * a) for v in col)
    d.rectangle(box, fill=(4, 20, 34), outline=tuple(int(v * a * .35) for v in col), width=2)
    for (px, py, dx, dy) in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        d.line([(px, py), (px + dx * k, py)], fill=cc, width=5); d.line([(px, py), (px, py + dy * k)], fill=cc, width=5)

def fmt(v, dec): return f"{v:,.{dec}f}"
def colr(ch): return UP if ch > 0 else DN if ch < 0 else FLAT
def arrow(ch): return "▲" if ch > 0 else "▼" if ch < 0 else "━"

def wrap(s, n):
    chunks, cur = [], ""
    for ch in s:
        cur += ch
        if ch in "、。": chunks.append(cur); cur = ""
    if cur: chunks.append(cur)
    lines, line = [], ""
    for c in chunks:
        if len(line) + len(c) <= n or (not line and len(c) <= n + 1): line += c; continue
        if line: lines.append(line)
        while len(c) > n + 1: lines.append(c[:n]); c = c[n:]
        line = c
    if line: lines.append(line)
    return lines

def card_rows(d, items, p, y0, kind):
    fN, fS, fV, fC = F("Bold", 40), FM(24), F("Black", 88), F("Bold", 38)
    for i, it in enumerate(items):
        a = ease((p - i * 0.22) / 0.25)
        if a <= 0: continue
        off = int((1 - a) * 120); y = y0 + i * 300
        frame_box(d, (70 + off, y, 1010 + off, y + 270), a=a)
        d.text((110 + off, y + 30), it["name"], font=fN, fill=WHITE)
        d.text((970 + off, y + 38), it["sub"], font=fS, fill=CY_D, anchor="ra")
        val = it["value"] * (0.97 + 0.03 * ease((p - i * 0.22) / 0.3))
        u = it.get("unit", "")
        vs = (u + fmt(val, it["dec"])) if u == "$" else (fmt(val, it["dec"]) + u)
        col = colr(it["chg"])
        d.text((110 + off, y + 170), vs, font=fV, fill=WHITE, anchor="ls")
        cl = it.get("chg_label") or f"{it['chg']:+,.2f} ({it['pct']:+.2f}%)"
        d.text((110 + off, y + 235), f"{arrow(it['chg'])} {cl}", font=fC, fill=col, anchor="ls")
        # 変化率ゲージ
        pct = it.get("pct", None)
        if pct is None: pct = (it["chg"] / (it["value"] - it["chg"]) * 100) if it["value"] != it["chg"] else 0
        gx, gy = 690 + off, y + 212; d.rectangle([gx, gy, gx + 280, gy + 14], fill=(12, 40, 58))
        d.line([(gx + 140, gy - 6), (gx + 140, gy + 20)], fill=CY_D, width=2)
        wlen = max(-140, min(140, pct / 1.0 * 140)) * a
        if wlen: d.rectangle([gx + 140 + min(0, wlen), gy, gx + 140 + max(0, wlen), gy + 14], fill=col)

def draw_scene(img, d, key, p, t, data):
    if key == "intro":
        f = FM(46); s = "> INITIALIZING MARKET SCAN..."
        n = int(len(s) * min(1, p * 2.2)); d.text((90, 900), s[:n] + ("_" if int(t * 3) % 2 else ""), font=f, fill=CY)
        for i, line in enumerate(["NYSE ........ ONLINE", "NASDAQ ...... ONLINE", "TREASURY .... ONLINE", "FX / CRYPTO . ONLINE"]):
            if p > 0.25 + i * 0.12: d.text((90, 990 + i * 70), line, font=FM(38), fill=(120, 220, 170))
        if p > 0.78:
            text_c(d, (540, 1420), "US MARKET BRIEF", F("Black", 92), WHITE, glow=(0, 70, 90))
            text_c(d, (540, 1520), data["date_label"], FM(52), CY)
    elif key == "headline":
        a = ease(p / 0.2)
        frame_box(d, (70, 820, 1010, 1560), a=a)
        text_c(d, (540, 900), "CONCLUSION", FM(40), CY)
        text_c(d, (540, 1060), "主要3指数", F("Black", 110), WHITE)
        hl = data.get("headline", {"status": "そろって続落", "dir": -1, "factor": "長期金利の上昇"})
        hc = UP if hl["dir"] > 0 else DN if hl["dir"] < 0 else FLAT
        fs = 124 if len(hl["status"]) <= 6 else int(124 * 6 / len(hl["status"]))
        if p > 0.18: text_c(d, (540, 1220), hl["status"], F("Black", fs), hc, glow=(0, 35, 80))
        if p > 0.55 and hl.get("factor"):
            ft = "要因：" + hl["factor"]; fz = 54 if len(ft) <= 12 else int(54 * 12 / len(ft))
            d.rounded_rectangle([130, 1340, 950, 1470], 20, fill=(60, 45, 0), outline=AMB, width=3)
            text_c(d, (540, 1405), ft, F("Bold", fz), AMB)
    elif key in ("indices", "rates_fx", "commodities"):
        card_rows(d, data[key], p * 1.3, 700, key)
    elif key == "analysis":
        text_c(d, (540, 740), "▍ KEY FACTORS", FM(46), CY, anchor="mm")
        for i, (h, b) in enumerate(data["analysis"]):
            a = ease((p * 1.2 - i * 0.25) / 0.2)
            if a <= 0: continue
            y = 830 + i * 270; off = int((1 - a) * 80)
            frame_box(d, (70, y + off, 1010, y + 230 + off), a=a)
            d.text((110, y + 40 + off), f"0{i+1}", font=FM(44), fill=CY)
            d.text((200, y + 30 + off), h, font=F("Black", 60), fill=WHITE)
            d.text((200, y + 125 + off), b, font=F("Bold", 46), fill=AMB if i == 2 else (180, 215, 230))
    elif key == "outro":
        a = ease(p / 0.2)
        frame_box(d, (70, 780, 1010, 1260), col=AMB, a=a)
        text_c(d, (540, 860), "NEXT EVENT", FM(44), AMB)
        text_c(d, (540, 1000), data["next"][0], F("Black", 100), WHITE)
        text_c(d, (540, 1150), data["next"][1], F("Black", 76), AMB)
        if p > 0.62:
            s = "数字は、嘘をつかない。"; n = int(len(s) * min(1, (p - 0.62) / 0.2))
            text_c(d, (540, 1420), s[:n], F("Black", 72), CY, glow=(0, 60, 80))

def main(dj, outp):
    data = json.load(open(dj)); wd = os.path.dirname(os.path.abspath(outp)) + "/_work"; os.makedirs(wd, exist_ok=True)
    TARGET = float(os.environ.get("TARGET_SEC", 60))
    speed = 1.3
    for _ in range(5):  # 読み上げ速度を調整して全体を TARGET 秒に収める
        clips, starts, t0 = [], [], 0.6
        for k in ORDER:
            a = synth(data["script"][k], f"{wd}/{k}.wav", speed)
            pad = 0.3 if k != "outro" else 1.2
            starts.append((k, t0, len(a) / SR, len(a) / SR + pad)); clips.append(a); t0 += len(a) / SR + pad
        speech = sum(len(a) for a in clips) / SR; fixed = t0 - speech
        if TARGET - 1.5 <= t0 <= TARGET - 0.2 or not (1.1 < speed < 1.7): break
        speed = min(1.7, max(1.1, speed * speech / (TARGET - 0.8 - fixed)))
    # 余りは最後の場面に足してぴったり TARGET 秒に
    k, s, d_, sl = starts[-1]; starts[-1] = (k, s, d_, sl + max(0, TARGET - t0)); t0 = max(t0, TARGET)
    print(f"speech speed={speed:.2f} total={t0:.1f}s")
    total = min(t0, TARGET) if t0 <= TARGET + 0.01 else t0; N = int(total * SR)
    voice = np.zeros(N, np.float32)
    for (k, s, dur, _), a in zip(starts, clips):
        i = int(s * SR); voice[i:i + len(a)] += a[:N - i]
    mix = voice * 0.95 + bgm(N, [s for _, s, _, _ in starts])
    mix = np.clip(mix, -1, 1)
    with wave.open(f"{wd}/mix.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    hop = SR // FPS; env = np.array([np.sqrt(np.mean(voice[i:i + hop] ** 2)) for i in range(0, N, hop)])
    env = np.clip(env / (env.max() + 1e-9) * 1.6, 0, 1)

    bg = make_bg(); nf = int(total * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", f"{wd}/mix.wav", "-c:v", "libx264", "-preset", "medium",
                           "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                           "-movflags", "+faststart", outp], stdin=subprocess.PIPE)
    fT, fTag, fSub, fSm = FM(30), FM(34), F("Bold", 48), F("Regular", 24)
    for fi in range(nf):
        t = fi / FPS; amp = env[min(fi, len(env) - 1)]
        cur = starts[0]
        for s in starts:
            if t >= s[1] - 0.25: cur = s
        k, s0, dur, slot = cur; p = max(0, (t - s0 + 0.25) / slot)
        img = bg.copy(); d = ImageDraw.Draw(img, "RGBA")
        for (x, y, sp, r) in PARTS:
            yy = (y - t * sp * 40) % H; d.ellipse([x - r, yy - r, x + r, yy + r], fill=(0, 229, 255, 70))
        # ヘッダー
        d.rectangle([0, 0, W, 110], fill=(2, 10, 20, 230)); d.line([(0, 110), (W, 110)], fill=CY_D, width=2)
        if int(t * 2) % 2: d.ellipse([40, 42, 64, 66], fill=UP)
        d.text((80, 55), "LIVE", font=fT, fill=WHITE, anchor="lm")
        d.text((540, 55), "AI MARKET NAVIGATOR", font=FM(34), fill=CY, anchor="mm")
        d.text((1040, 55), data["date_label"][:10], font=fT, fill=(150, 190, 205), anchor="rm")
        # アバター
        big = k == "intro"
        av = avatar(amp, t, big); img.paste(av, (540 - 280, 370 - 280 + (60 if big else 0)), av)
        d.text((540, 660 if not big else 720), f"[ {TAGS[k]} ]", font=fTag, fill=CY, anchor="mm")
        # シーン
        draw_scene(img, d, k, p, t, data)
        # 字幕
        sub = data["subs"][k]; rev = int(len(sub) * min(1, max(0, (t - s0) / (dur * 0.85))))
        lines = wrap(sub, 20)
        cnt = 0; shown = []
        for l in lines:
            if cnt >= rev: break
            shown.append(l[:rev - cnt]); cnt += len(l)
        shown = shown[-2:]
        if shown:
            d.rectangle([40, 1650, 1040, 1830], fill=(0, 0, 0, 170)); d.line([(40, 1650), (40, 1830)], fill=CY, width=6)
            for i, l in enumerate(shown): d.text((80, 1690 + i * 70), l, font=fSub, fill=WHITE)
        d.text((540, 1880), "※情報提供のみを目的としたもので投資助言ではありません", font=fSm, fill=(110, 140, 155), anchor="mm")
        # グリッチ
        if (t - s0) < 0.18 and k != "intro":
            arr = np.asarray(img).copy()
            for _ in range(6):
                y = random.randint(0, H - 40); h = random.randint(6, 30); sh = random.randint(-40, 40)
                arr[y:y + h] = np.roll(arr[y:y + h], sh, axis=1)
            arr[:, :, 2] = np.roll(arr[:, :, 2], 6, axis=1); img = Image.fromarray(arr)
        ff.stdin.write(img.tobytes())
    ff.stdin.close(); ff.wait()
    print(f"done: {outp} ({total:.1f}s)")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data.json", sys.argv[2] if len(sys.argv) > 2 else "out.mp4")
