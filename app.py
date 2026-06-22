import webview
import threading
import json
import os
import random
import string
import winreg as reg
import sys
import logging
import uuid
import requests
from tkinter import filedialog
import tkinter as tk

# Импорт логики из основного скрипта
import game_alerter

class Api:
    def __init__(self, window):
        self.window = window
        self.config = game_alerter.global_config if hasattr(game_alerter, 'global_config') else {}
        if not self.config:
            self.config = game_alerter.load_config()
            game_alerter.global_config = self.config
            
        if "device_id" not in self.config:
            self.config["device_id"] = str(uuid.uuid4())
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            game_alerter.global_config["device_id"] = self.config["device_id"]

    def minimize(self):
        self.window.minimize()

    def close(self):
        self.window.destroy()

    def get_config(self):
        return self.config

    def log_action(self, msg):
        logging.info(f"[UI] {msg}")

    def select_wow_path(self):
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            title="Выберите WoWChatLog.txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        if file_path:
            self.config["wow_log_path"] = file_path
            game_alerter.global_config["wow_log_path"] = file_path
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            return {"success": True, "path": file_path}
        return {"success": False}

    def generate_tg_code(self):
        # Всегда генерируем свежий код, так как он живет 10 минут на сервере
        code = '-'.join(''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(2))
        
        device_id = self.config.get("device_id")
        try:
            url = "https://gamealerter-api-auto.didur-danil.workers.dev/api/pair"
            requests.post(url, json={"device_id": device_id, "code": code}, timeout=5)
        except Exception as e:
            self.log_action(f"Ошибка привязки кода на сервере: {e}")
            
        return code

    def check_link_status(self):
        device_id = self.config.get("device_id")
        if not device_id:
            return {"linked": False}
            
        try:
            url = "https://gamealerter-api-auto.didur-danil.workers.dev/api/status"
            resp = requests.post(url, json={"device_id": device_id}, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            self.log_action(f"Ошибка проверки статуса: {e}")
            
        return {"linked": False}

    def update_setting(self, key, value):
        self.config[key] = value
        game_alerter.global_config[key] = value
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)
            
        if key == "autostart_enabled":
            self.set_autostart(value)
            
        return True

    def set_autostart(self, enable):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "GameAlerter"
        try:
            if getattr(sys, 'frozen', False):
                # Если скомпилировано в exe (PyInstaller)
                app_path = f'"{sys.executable}"'
            else:
                # Если запускаем через python
                python_exe = sys.executable.replace("python.exe", "pythonw.exe")
                app_path = f'"{python_exe}" "{os.path.abspath("app.py")}"'
            
            key = reg.OpenKey(reg.HKEY_CURRENT_USER, key_path, 0, reg.KEY_ALL_ACCESS)
            if enable:
                reg.SetValueEx(key, app_name, 0, reg.REG_SZ, app_path)
            else:
                try:
                    reg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            reg.CloseKey(key)
        except Exception as e:
            print(f"Автозапуск ошибка: {e}")

def get_web_dir():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'web')
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), 'web')

def start_gui():
    api = Api(None)
    
    # Запускаем фоновый мониторинг (Алертер)
    game_alerter.start_background_monitor()
    
    index_path = os.path.join(get_web_dir(), "index.html")
    
    # Флаг frameless убирает стандартную рамку Windows
    window = webview.create_window(
        "GameAlerter",
        url=index_path, 
        js_api=api, 
        width=900, 
        height=600, 
        frameless=True, 
        easy_drag=False,
        background_color='#0f1115'
    )
    api.window = window
    webview.start(debug=False)

if __name__ == '__main__':
    # Запускаем красивый UI (алертер запустится внутри start_gui)
    start_gui()
