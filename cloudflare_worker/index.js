export default {
  async fetch(request, env, ctx) {
    const BOT_TOKEN = "8719278182:AAELhXhPKCXvLurCV5KsDrtaqRpfP6I-FQg";
    const url = new URL(request.url);

    if (url.pathname === "/webhook") {
      if (request.method !== "POST") return new Response("OK");
      try {
        const update = await request.json();
        if (update.message && update.message.text) {
          const text = update.message.text;
          const chatId = update.message.chat.id;

          let cleanText = text.trim().toUpperCase();
          // Удаляем /start если пользователь написал с ним
          if (cleanText.startsWith("/START ")) {
            cleanText = cleanText.replace("/START ", "").trim();
          }

          if (cleanText === "/CODE") {
            await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                chat_id: chatId,
                text: "Пожалуйста, введите ваш 8-значный код из приложения для привязки:"
              })
            });
            return new Response("OK");
          }

          // Регулярка: 4 символа, опциональное тире, 4 символа
          const codeRegex = /^([A-Z0-9]{4})-?([A-Z0-9]{4})$/;
          const match = cleanText.match(codeRegex);

          if (match) {
            // Нормализуем код: всегда добавляем тире, чтобы совпадало с тем, что отправляет десктоп
            const normalizedCode = match[1] + "-" + match[2];
            
            await env.DB.put(normalizedCode, chatId.toString());
            await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                chat_id: chatId,
                text: "✅ Приложение GameAlerter успешно привязано!\nТеперь ты будешь получать сюда уведомления из игры."
              })
            });
          } else {
            await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                chat_id: chatId,
                text: "Привет! 👋\nЯ бот GameAlerter. Просто отправь мне свой 8-значный код из настроек приложения (с тире или без), чтобы получать уведомления.\nНапример: AB12-CD34 или AB12CD34"
              })
            });
          }
        }
      } catch (e) {
        // Логируем ошибку в Cloudflare
        console.error(e.stack);
      }
      return new Response("OK");
    }

    if (url.pathname === "/notify") {
      if (request.method !== "POST") return new Response("Error");
      const body = await request.json();
      const code = body.code;
      const message = body.message;

      if (code && message) {
        const chatId = await env.DB.get(code);
        if (chatId) {
          await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: chatId, text: message })
          });
          return new Response("Sent", {status: 200});
        }
      }
      return new Response("Not found", {status: 404});
    }

    return new Response("GameAlerter Cloud API is running!");
  }
};
