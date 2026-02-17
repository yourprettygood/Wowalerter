import json
import time

import cv2
import numpy as np
from mss import mss

CONFIG = "config.json"
TEMPLATE_PATH = "templates/Instance.png"  # если у тебя другое имя — поправь

# Настройки детекта
THRESHOLD = 0.90        # начни с 0.90, потом подстроим
INTERVAL = 0.25         # как часто проверять (сек)
CONFIRM_FRAMES = 3      # сколько раз подряд должно совпасть
COOLDOWN = 15           # пауза после срабатывания (сек)

def preprocess_bgr(img_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Нормализация помогает, когда фон "просвечивает"
    gray = cv2.equalizeHist(gray)
    return gray

def match_score(img_gray: np.ndarray, tpl_gray: np.ndarray) -> float:
    res = cv2.matchTemplate(img_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
    return float(res.max())

def beep():
    try:
        import winsound
        winsound.Beep(1200, 250)
        winsound.Beep(1200, 250)
    except Exception:
        pass

def main():
    cfg = json.load(open(CONFIG, "r", encoding="utf-8"))
    roi = cfg["roi"]

    tpl_bgr = cv2.imread(TEMPLATE_PATH)
    if tpl_bgr is None:
        raise SystemExit(f"Не найден шаблон: {TEMPLATE_PATH}")

    tpl = preprocess_bgr(tpl_bgr)

    sct = mss()
    hits = 0
    last_fire = 0.0

    print("Detector running. Ctrl+C to stop.")
    print("ROI:", roi)

    while True:
        now = time.time()
        if now - last_fire < COOLDOWN:
            time.sleep(INTERVAL)
            continue

        frame = np.array(sct.grab(roi))  # BGRA
        bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        img = preprocess_bgr(bgr)

        score = match_score(img, tpl)

        if score >= THRESHOLD:
            hits += 1
        else:
            hits = 0

        if hits >= CONFIRM_FRAMES:
            print(f"[FOUND] score={score:.3f} time={time.strftime('%H:%M:%S')}")
            beep()
            last_fire = time.time()
            hits = 0

        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
