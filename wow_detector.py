import os
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from mss import mss

# ================== НАСТРОЙКИ ==================
TEMPLATE_PATH = "templates/Instance.png"

# Глобальный поиск: делаем редко и на уменьшенной копии
DOWNSCALE_WIDTH = 960
GLOBAL_INTERVAL = 1.0

# Ищем только там, где появляется окно (верхний центр)
# x, y, w, h в долях экрана
SEARCH_CENTER = True
CENTER_BOX = (0.25, 0.05, 0.50, 0.45)  # верхняя центральная область

# Трекинг найденной зоны (после нахождения кнопки)
TRACK_INTERVAL = 0.25
TRACK_MARGIN = 240
LOST_LIMIT = 12

# Масштабы (лёгкий диапазон)
SCALES = [0.80, 0.90, 1.00, 1.10, 1.20]

# ВАЖНО: твой реальный score ≈ 0.60, поэтому ставим порог около него
THRESHOLD = 0.60
CONFIRM_FRAMES = 3

COOLDOWN = 15  # антиспам (сек)

# ===== DEBUG (пока тестишь оставь True, потом выключишь) =====
DEBUG = True
DEBUG_DIR = "debug"
DEBUG_MIN_SCORE = 0.50
DEBUG_COOLDOWN = 3.0
# ============================================================


def preprocess_bgr(img_bgr: np.ndarray) -> np.ndarray:
    # Более стабильная предобработка под текст/кнопку
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    gray = cv2.equalizeHist(gray)
    # бинаризация помогает именно по UI-кнопкам
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return bw


def beep():
    try:
        import winsound
        winsound.Beep(1200, 250)
        winsound.Beep(1200, 250)
    except Exception:
        pass


@dataclass
class Match:
    score: float
    loc: Tuple[int, int]        # (x, y) на текущем изображении
    scale: float
    tpl_wh: Tuple[int, int]     # (w, h) шаблона в текущем масштабе


def build_scaled_templates(tpl_gray: np.ndarray, scales: List[float]) -> List[Tuple[float, np.ndarray]]:
    out = []
    h, w = tpl_gray.shape[:2]
    for s in scales:
        nw = max(8, int(w * s))
        nh = max(8, int(h * s))
        scaled = cv2.resize(tpl_gray, (nw, nh), interpolation=cv2.INTER_AREA)
        out.append((s, scaled))
    return out


def match_best(img_gray: np.ndarray, scaled_templates: List[Tuple[float, np.ndarray]]) -> Optional[Match]:
    ih, iw = img_gray.shape[:2]
    best: Optional[Match] = None

    for s, tpl in scaled_templates:
        th, tw = tpl.shape[:2]
        if tw > iw or th > ih:
            continue

        res = cv2.matchTemplate(img_gray, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if best is None or max_val > best.score:
            best = Match(float(max_val), (int(max_loc[0]), int(max_loc[1])), s, (tw, th))

    return best


def clamp_roi(left: int, top: int, width: int, height: int, max_w: int, max_h: int) -> dict:
    left = max(0, min(left, max_w - 1))
    top = max(0, min(top, max_h - 1))
    width = max(1, min(width, max_w - left))
    height = max(1, min(height, max_h - top))
    return {"left": left, "top": top, "width": width, "height": height}


def grab_bgr(sct: mss, roi: dict) -> np.ndarray:
    frame = np.array(sct.grab(roi))  # BGRA
    return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)


def downscale_keep_aspect(img_bgr: np.ndarray, target_w: int) -> Tuple[np.ndarray, float]:
    h, w = img_bgr.shape[:2]
    if w <= target_w:
        return img_bgr, 1.0
    scale = target_w / float(w)
    nh = max(1, int(h * scale))
    small = cv2.resize(img_bgr, (target_w, nh), interpolation=cv2.INTER_AREA)
    return small, scale  # small_w / orig_w


def save_debug(small_bgr: np.ndarray, bgr_full: np.ndarray, best: Match, tag: str) -> None:
    os.makedirs(DEBUG_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    x, y = best.loc
    w, h = best.tpl_wh

    overlay = small_bgr.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 0, 255), 2)
    crop = small_bgr[max(0, y): y + h, max(0, x): x + w].copy()

    p1 = os.path.join(DEBUG_DIR, f"{ts}_{tag}_debug_screen.png")
    p2 = os.path.join(DEBUG_DIR, f"{ts}_{tag}_debug_small.png")
    p3 = os.path.join(DEBUG_DIR, f"{ts}_{tag}_debug_overlay.png")
    p4 = os.path.join(DEBUG_DIR, f"{ts}_{tag}_debug_match.png")

    cv2.imwrite(p1, bgr_full)
    cv2.imwrite(p2, small_bgr)
    cv2.imwrite(p3, overlay)
    cv2.imwrite(p4, crop)

    print(f"[DEBUG SAVED] {p3}  {p4}")


def main():
    tpl_bgr = cv2.imread(TEMPLATE_PATH)
    if tpl_bgr is None:
        raise SystemExit(f"Не найден шаблон: {TEMPLATE_PATH}")

    tpl_proc = preprocess_bgr(tpl_bgr)
    scaled_templates = build_scaled_templates(tpl_proc, SCALES)

    sct = mss()
    mon = sct.monitors[1]  # основной монитор
    full_roi = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}

    print("Detector running. Ctrl+C to stop.")
    print("Template:", TEMPLATE_PATH)
    print("Screen:", (full_roi["width"], full_roi["height"]))
    print(f"threshold={THRESHOLD} confirm={CONFIRM_FRAMES} scales={SCALES}")
    print(f"CENTER_BOX={CENTER_BOX}")

    mode = "GLOBAL"
    track_roi: Optional[dict] = None
    track_tpl: Optional[np.ndarray] = None
    hits = 0
    lost = 0
    last_fire = 0.0
    last_debug = 0.0

    while True:
        try:
            now = time.time()
            if now - last_fire < COOLDOWN:
                time.sleep(TRACK_INTERVAL)
                continue

            if mode == "GLOBAL":
                # ограничиваем поиск верхним центром
                if SEARCH_CENTER:
                    x, y, w, h = CENTER_BOX
                    roi = {
                        "left": full_roi["left"] + int(full_roi["width"] * x),
                        "top": full_roi["top"] + int(full_roi["height"] * y),
                        "width": int(full_roi["width"] * w),
                        "height": int(full_roi["height"] * h),
                    }
                else:
                    roi = full_roi

                bgr_full = grab_bgr(sct, roi)
                small_bgr, small_scale = downscale_keep_aspect(bgr_full, DOWNSCALE_WIDTH)
                small_proc = preprocess_bgr(small_bgr)

                best = match_best(small_proc, scaled_templates)

                if best and best.score >= THRESHOLD:
                    hits += 1
                else:
                    hits = 0

                if best:
                    print(f"[GLOBAL] score={best.score:.3f} hits={hits}/{CONFIRM_FRAMES} scale={best.scale}")
                    if (
                        DEBUG
                        and best.score >= DEBUG_MIN_SCORE
                        and (now - last_debug) >= DEBUG_COOLDOWN
                        and best.score < THRESHOLD
                    ):
                        save_debug(small_bgr, bgr_full, best, tag=f"s{best.scale}_sc{best.score:.3f}")
                        last_debug = now

                if best and hits >= CONFIRM_FRAMES:
                    inv = 1.0 / small_scale
                    x_small, y_small = best.loc
                    tw, th = best.tpl_wh

                    # координаты относительно roi -> переводим в систему full_roi
                    x_full = int(x_small * inv) + (roi["left"] - full_roi["left"])
                    y_full = int(y_small * inv) + (roi["top"] - full_roi["top"])
                    w_full = int(tw * inv)
                    h_full = int(th * inv)

                    left = x_full - TRACK_MARGIN
                    top = y_full - TRACK_MARGIN
                    width = w_full + 2 * TRACK_MARGIN
                    height = h_full + 2 * TRACK_MARGIN

                    track_roi = clamp_roi(left, top, width, height, full_roi["width"], full_roi["height"])
                    track_tpl = dict(scaled_templates)[best.scale]

                    mode = "TRACK"
                    hits = 0
                    lost = 0

                    print(f"[FOUND] score={best.score:.3f} roi={track_roi} time={time.strftime('%H:%M:%S')}")
                    beep()
                    last_fire = time.time()

                time.sleep(GLOBAL_INTERVAL)

            else:  # TRACK
                assert track_roi is not None and track_tpl is not None

                bgr = grab_bgr(sct, track_roi)
                proc = preprocess_bgr(bgr)

                best = match_best(proc, [(1.0, track_tpl)])
                ok = bool(best and best.score >= THRESHOLD)

                if ok:
                    lost = 0
                else:
                    lost += 1

                if lost >= LOST_LIMIT:
                    print("[TRACK] lost -> back to GLOBAL")
                    mode = "GLOBAL"
                    track_roi = None
                    track_tpl = None
                    hits = 0
                    lost = 0

                time.sleep(TRACK_INTERVAL)

        except KeyboardInterrupt:
            print("Stopped.")
            break
        except Exception as e:
            print("Loop error:", repr(e))
            time.sleep(1.0)


if __name__ == "__main__":
    main()
