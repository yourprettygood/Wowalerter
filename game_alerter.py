import time
import json
import logging
import win32api
import win32con
import win32gui
import os
import ctypes
import threading
import pystray
from PIL import Image, ImageDraw
import requests

# Настройка логирования в файл
os.makedirs(".scratchpad", exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(".scratchpad/alerter.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

CONFIG_FILE = "config.json"
app_running = True
tray_icon = None
global_config = {}

recent_whisper_text = ""
recent_whisper_time = 0

def get_idle_time():
    try:
        last_input = win32api.GetLastInputInfo()
        current_tick = win32api.GetTickCount()
        # Избегаем отрицательных значений при переполнении счетчика (49.7 дней)
        elapsed = current_tick - last_input
        if elapsed < 0:
            elapsed = 0
        return elapsed / 1000.0
    except Exception as e:
        logging.error(f"Ошибка получения AFK статуса: {e}")
        return 0

def should_send_alert(alert_type):
    if alert_type == 'rc' and not global_config.get("rc_enabled", True):
        return False
    if alert_type == 'whisper' and not global_config.get("whisper_enabled", True):
        return False
        
    if global_config.get("afk_enabled", False):
        idle_seconds = get_idle_time()
        if idle_seconds < 180: # 3 минуты
            logging.info(f"Алерт ({alert_type}) проигнорирован: Пользователь не AFK (простой: {int(idle_seconds)}с)")
            return False
            
    return True

def send_telegram_message(text):
    device_id = global_config.get("device_id", "")
    
    if not device_id:
        logging.warning("Нет device_id, алерт не отправлен")
        return
        
    def _send():
        try:
            url = "https://gamealerter-api-auto.didur-danil.workers.dev/notify"
            payload = {"device_id": device_id, "message": text}
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logging.error(f"Ошибка отправки в облако: {e}")
            
    threading.Thread(target=_send, daemon=True).start()

def chatlog_monitor():
    global recent_whisper_text, recent_whisper_time
    
    last_size = -1
    while app_running:
        log_path = global_config.get("wow_log_path", "")
        if not log_path or not os.path.exists(log_path):
            time.sleep(2)
            continue
            
        try:
            current_size = os.path.getsize(log_path)
            
            # Если это первый запуск (last_size == -1), просто запоминаем размер файла
            # и не читаем его целиком, чтобы не было зависаний.
            if last_size == -1:
                last_size = current_size
                time.sleep(1)
                continue
                
            if current_size < last_size:
                last_size = 0
            
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(last_size)
                
                for line in f:
                    if " шепчет: " in line or " whispers: " in line:
                        current_time = time.time()
                        w_text = line.strip()
                        
                        if "  " in w_text:
                            w_text = w_text.split("  ", 1)[-1]
                        
                        if w_text and w_text != recent_whisper_text and (current_time - recent_whisper_time > 5):
                            recent_whisper_text = w_text
                            recent_whisper_time = current_time
                            logging.info(f"Новое сообщение: {w_text}")
                            if should_send_alert('whisper'):
                                send_telegram_message(f"✉️ Личное сообщение:\n{w_text}")
                                
                last_size = f.tell()
                        
                if tray_icon:
                            tray_icon.icon = create_image(color=(40, 100, 200))
                            def reset_icon_chat():
                                time.sleep(2)
                                if tray_icon:
                                    tray_icon.icon = create_image(color=(200, 40, 40))
                            threading.Thread(target=reset_icon_chat, daemon=True).start()
        except Exception as e:
            logging.error(f"Ошибка чтения лога: {e}")
        
        time.sleep(1)

def load_config():
    default_config = {
        "games": [
            {"window_title": "World of Warcraft"}
        ],
        "cooldown_seconds": 15,
        "afk_enabled": False,
        "rc_enabled": True,
        "whisper_enabled": True,
        "wow_log_path": ""
    }
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4)
        return default_config
        
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return default_config

class SystemGameAlerter:
    def __init__(self, config):
        self.config = config
        self.last_alert_time = 0
        self.cooldown = config.get("cooldown_seconds", 15)
        self.window_creation_times = {}
        
        self.WM_SHELLHOOKMESSAGE = win32gui.RegisterWindowMessage("SHELLHOOK")
        
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = {self.WM_SHELLHOOKMESSAGE: self.on_shell_hook}
        wc.lpszClassName = "SystemGameAlerterHook"
        wc.hInstance = win32api.GetModuleHandle(None)
        
        self.class_atom = win32gui.RegisterClass(wc)
        self.hwnd = win32gui.CreateWindow(
            self.class_atom,
            "GameAlerterListener",
            0, 0, 0,
            win32con.CW_USEDEFAULT, win32con.CW_USEDEFAULT,
            0, 0, wc.hInstance, None
        )
        
        ctypes.windll.user32.RegisterShellHookWindow(self.hwnd)
        logging.info("Системный мониторинг запущен. Ожидаем события (РЧ, прок инста)...")

    def on_shell_hook(self, hwnd, msg, wparam, lparam):
        try:
            title = win32gui.GetWindowText(lparam)
            HSHELL_WINDOWCREATED = 1
            HSHELL_REDRAW = 6
            
            if title and "warcraft" in title.lower():
                if wparam == HSHELL_WINDOWCREATED:
                    self.window_creation_times[lparam] = time.time()
                
                elif wparam == HSHELL_REDRAW:
                    creation_time = self.window_creation_times.get(lparam, 0)
                    if (time.time() - creation_time) >= 15.0:
                        logging.info(f"Обнаружен HSHELL_REDRAW для окна: {title}. Отправляем пуш!")
                        if should_send_alert('rc'):
                            self.trigger_alert(title)
        except Exception as e:
            pass
        return True

    def trigger_alert(self, game_name):
        global tray_icon
        
        logging.info(f"АЛЕРТ (РЧ/ИНСТ) для {game_name}")
        send_telegram_message(f"🚨 Готовность в подземелье/рейд!\nОкно: {game_name}")
        
        if tray_icon:
            tray_icon.icon = create_image(color=(40, 200, 40))
            def reset_icon():
                time.sleep(2)
                if tray_icon:
                    tray_icon.icon = create_image(color=(200, 40, 40))
            threading.Thread(target=reset_icon, daemon=True).start()

    def run(self):
        global app_running
        while app_running:
            win32gui.PumpWaitingMessages()
            time.sleep(0.1)

def run_alerter_thread(config):
    alerter = SystemGameAlerter(config)
    alerter.run()

def create_image(color=(200, 40, 40)):
    image = Image.new('RGB', (64, 64), color=(30, 30, 30))
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (8, 8, 56, 56),
        fill=color
    )
    return image

def on_quit(icon, item):
    global app_running
    app_running = False
    icon.stop()

def start_background_monitor():
    global tray_icon, global_config
    logging.info("=== System Game Alerter ===")
    global_config = load_config()
    
    threading.Thread(target=chatlog_monitor, daemon=True).start()
    t_alerter = threading.Thread(target=run_alerter_thread, args=(global_config,), daemon=True)
    t_alerter.start()
    
    tray_icon = pystray.Icon(
        "wowalerter",
        create_image(),
        "WowAlerter",
        menu=pystray.Menu(
            pystray.MenuItem("Остановить (Выход)", on_quit)
        )
    )
    
    try:
        # Запускаем иконку (не блокирует поток)
        tray_icon.run_detached()
    except Exception as e:
        logging.error(f"Ошибка запуска иконки: {e}")

def main():
    start_background_monitor()
    while app_running:
        time.sleep(1)

if __name__ == "__main__":
    main()
