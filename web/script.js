const app = {
    // Навигация по экранам
    showScreen(screenId) {
        document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
        document.getElementById(screenId).classList.add('active');
    },

    // Вкладки внутри дашборда
    switchTab(e, tabId) {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        
        if (e && e.currentTarget) {
            e.currentTarget.classList.add('active');
        }
        document.getElementById(tabId).classList.add('active');
    },

    loginGuest() {
        // Логика перехода на выбор игр
        this.showScreen('screen-games');
    },

    selectGame(gameId) {
        if(gameId === 'wow_wotlk') {
            document.body.className = 'theme-wotlk';
            document.getElementById('active-game-title').innerText = "WotLK 3.3.5";
            this.showScreen('screen-dashboard');
            
            // Если pywebview загружен, сообщаем питону о смене игры
            if (window.pywebview) {
                window.pywebview.api.log_action("Game Selected: " + gameId);
            }
        }
    },

    logout() {
        document.body.className = 'theme-default';
        this.showScreen('screen-games');
    },

    // Вызовы Python API
    async setupLogs() {
        if(window.pywebview) {
            let res = await window.pywebview.api.select_wow_path();
            if(res.success) {
                const dot = document.getElementById('logs-status-dot');
                const txt = document.getElementById('logs-status-text');
                dot.className = "dot green";
                txt.innerText = "Логи подключены: " + res.path;
            }
        } else {
            alert("API не доступно (запущено в браузере?)");
        }
    },

    async generateTgCode() {
        if(window.pywebview) {
            let code = await window.pywebview.api.generate_tg_code();
            document.getElementById('tg-auth-code').innerText = code;
        } else {
            // Фейк для браузера
            document.getElementById('tg-auth-code').innerText = "M7-K2-X9-A1";
        }
    },

    async updateSetting(key, value) {
        if(window.pywebview) {
            await window.pywebview.api.update_setting(key, value);
        }
    }
};

// Инициализация при готовности pywebview
window.addEventListener('pywebviewready', async function() {
    console.log("Python backend is ready!");
    const config = await window.pywebview.api.get_config();
    if (config) {
        if (config.rc_enabled !== undefined) document.getElementById('toggle-rc').checked = config.rc_enabled;
        if (config.whisper_enabled !== undefined) document.getElementById('toggle-whisper').checked = config.whisper_enabled;
        if (config.afk_enabled !== undefined) document.getElementById('toggle-afk').checked = config.afk_enabled;
        if (config.autostart_enabled !== undefined) document.getElementById('toggle-autostart').checked = config.autostart_enabled;
        
        if (config.telegram_auth_code) {
            document.getElementById('tg-auth-code').innerText = config.telegram_auth_code;
        }
        if (config.wow_log_path) {
            const dot = document.getElementById('logs-status-dot');
            const txt = document.getElementById('logs-status-text');
            dot.className = "dot green";
            txt.innerText = "Логи подключены: " + config.wow_log_path;
        }
    }
});
