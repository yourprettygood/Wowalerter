import json
import cv2
import numpy as np
from mss import mss

OUT_FILE = "config.json"

def main():
    sct = mss()
    mon = sct.monitors[1]  # основной монитор
    frame = np.array(sct.grab(mon))  # BGRA
    img = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    print("Выдели мышкой прямоугольник вокруг окна 'Найдено подземелье' (или где оно появляется).")
    print("Enter/Space — подтвердить, Esc — отмена.")

    r = cv2.selectROI("Select ROI", img, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()

    x, y, w, h = map(int, r)
    if w == 0 or h == 0:
        print("ROI не выбран.")
        return

    cfg = {"roi": {"left": x, "top": y, "width": w, "height": h}}
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    print("Сохранено в", OUT_FILE, cfg)

if __name__ == "__main__":
    main()
