import json
from pathlib import Path

import cv2
import numpy as np
from mss import mss

CONFIG = "config.json"
OUT_DIR = Path("templates")
OUT_DIR.mkdir(exist_ok=True)

def main():
    cfg = json.load(open(CONFIG, "r", encoding="utf-8"))
    roi = cfg["roi"]

    sct = mss()
    frame = np.array(sct.grab(roi))  # BGRA
    img = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    print("Выдели мышкой ТОЛЬКО область с текстом кнопки (лучше 'В подземелье').")
    print("Enter/Space — сохранить, Esc — отмена.")

    r = cv2.selectROI("Select TEMPLATE", img, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()

    x, y, w, h = map(int, r)
    if w == 0 or h == 0:
        print("Шаблон не выбран.")
        return

    crop = img[y:y+h, x:x+w]
    out_path = OUT_DIR / "tpl_enter_text.png"
    cv2.imwrite(str(out_path), crop)
    print("Сохранено:", out_path)

if __name__ == "__main__":
    main()
