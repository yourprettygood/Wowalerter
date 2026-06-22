export default {
  async fetch(request, env, ctx) {
    const BOT_TOKEN = "8719278182:AAELhXhPKCXvLurCV5KsDrtaqRpfP6I-FQg";
    const ENABLE_COOLDOWN = false; // Юзер просил пока не включать, но реализовать на бис
    const url = new URL(request.url);

    // Вспомогательная функция для отправки сообщений в Telegram
    const sendTg = async (chatId, text) => {
      try {
        await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_id: chatId, text: text })
        });
      } catch (e) {
        console.error("TG Send Error: ", e);
      }
    };

    // Вебхук от Telegram
    if (url.pathname === "/webhook") {
      if (request.method !== "POST") return new Response("OK");
      try {
        const update = await request.json();
        if (update.message && update.message.text) {
          const text = update.message.text;
          const chatId = update.message.chat.id.toString();
          const username = update.message.chat.username ? `@${update.message.chat.username}` : `ID:${chatId}`;

          let cleanText = text.trim().toUpperCase();
          if (cleanText.startsWith("/START")) {
            cleanText = cleanText.replace("/START", "").trim();
          }

          if (cleanText === "/UNLINK") {
            const currentDevice = await env.DB.get(`tg:${chatId}`);
            if (currentDevice) {
              if (ENABLE_COOLDOWN) {
                const lastLinkStr = await env.DB.get(`last_link_time:${chatId}`);
                if (lastLinkStr) {
                  const lastLink = parseInt(lastLinkStr, 10);
                  const cooldownMs = 7 * 24 * 60 * 60 * 1000;
                  const timePassed = Date.now() - lastLink;
                  
                  if (timePassed < cooldownMs) {
                    const daysLeft = Math.ceil((cooldownMs - timePassed) / (1000 * 60 * 60 * 24));
                    await sendTg(chatId, `⏳ Вы не можете менять ПК так часто. Осталось ждать: ${daysLeft} дн.`);
                    return new Response("OK");
                  }
                }
              }

              await env.DB.delete(`tg:${chatId}`);
              await env.DB.delete(`device:${currentDevice}`);
              await sendTg(chatId, "🔌 Ваш старый ПК успешно отвязан. Теперь вы можете привязать новый, отправив его 8-значный код.");
            } else {
              await sendTg(chatId, "У вас нет привязанного ПК.");
            }
            return new Response("OK");
          }

          if (cleanText === "/CODE" || cleanText === "") {
            await sendTg(chatId, "Пожалуйста, введите ваш 8-значный код из приложения для привязки (например: AB12-CD34):");
            return new Response("OK");
          }

          // Регулярка для кода
          const codeRegex = /^([A-Z0-9]{4})-?([A-Z0-9]{4})$/;
          const match = cleanText.match(codeRegex);

          if (match) {
            const normalizedCode = match[1] + "-" + match[2];
            
            // Проверяем, есть ли такой код ожидания привязки
            const deviceId = await env.DB.get(`pairing_code:${normalizedCode}`);
            if (!deviceId) {
              await sendTg(chatId, "❌ Код недействителен или устарел. Перезапустите приложение на ПК, чтобы получить новый.");
              return new Response("OK");
            }

            // Проверяем лимит: 1 ПК на 1 аккаунт
            const existingDevice = await env.DB.get(`tg:${chatId}`);
            if (existingDevice && existingDevice !== deviceId) {
              await sendTg(chatId, "⚠️ К вашему Telegram уже привязан другой компьютер!\n1 аккаунт = 1 компьютер.\n\nОтправьте команду /unlink чтобы отвязать старый ПК, а затем снова введите код.");
              return new Response("OK");
            }

            // Проверяем, не привязан ли этот конкретный ПК к ДРУГОМУ телеграм аккаунту (чтобы не было dangling references)
            const deviceDataStr = await env.DB.get(`device:${deviceId}`);
            if (deviceDataStr) {
               const deviceData = JSON.parse(deviceDataStr);
               if (deviceData.chatId && deviceData.chatId !== chatId) {
                 await env.DB.delete(`tg:${deviceData.chatId}`);
                 await sendTg(deviceData.chatId, "🔌 Ваш ПК был привязан к другому аккаунту. Уведомления отключены.");
               }
            }

            // Успешная привязка
            await env.DB.put(`tg:${chatId}`, deviceId);
            await env.DB.put(`device:${deviceId}`, JSON.stringify({ chatId: chatId, username: username }));
            await env.DB.put(`last_link_time:${chatId}`, Date.now().toString());
            await env.DB.delete(`pairing_code:${normalizedCode}`);

            await sendTg(chatId, "✅ Компьютер успешно привязан!\nТеперь уведомления из игры будут приходить сюда.");
          } else {
            await sendTg(chatId, "Привет! 👋\nОтправь мне 8-значный код из приложения, чтобы привязать этот ПК.\nПример: AB12-CD34\nЕсли хочешь отвязать старый ПК, напиши /unlink");
          }
        }
      } catch (e) {
        console.error(e.stack);
      }
      return new Response("OK");
    }

    // Регистрация кода ожидающей привязки от ПК
    if (url.pathname === "/api/pair") {
      if (request.method !== "POST") return new Response(JSON.stringify({error: "Method Not Allowed"}), { status: 405 });
      try {
        const body = await request.json();
        if (body.device_id && body.code) {
          // Код живет 10 минут (600 секунд)
          await env.DB.put(`pairing_code:${body.code}`, body.device_id, { expirationTtl: 600 });
          return new Response(JSON.stringify({ success: true }), { headers: { "Content-Type": "application/json" } });
        }
      } catch (e) {
        return new Response(JSON.stringify({error: "Bad request"}), { status: 400 });
      }
      return new Response(JSON.stringify({error: "Invalid parameters"}), { status: 400 });
    }

    // Проверка статуса привязки от ПК
    if (url.pathname === "/api/status") {
      if (request.method !== "POST") return new Response(JSON.stringify({error: "Method Not Allowed"}), { status: 405 });
      try {
        const body = await request.json();
        if (body.device_id) {
          const deviceDataStr = await env.DB.get(`device:${body.device_id}`);
          if (deviceDataStr) {
            const deviceData = JSON.parse(deviceDataStr);
            return new Response(JSON.stringify({ linked: true, username: deviceData.username }), { headers: { "Content-Type": "application/json" } });
          } else {
            return new Response(JSON.stringify({ linked: false }), { headers: { "Content-Type": "application/json" } });
          }
        }
      } catch (e) {
        return new Response(JSON.stringify({error: "Bad request"}), { status: 400 });
      }
      return new Response(JSON.stringify({error: "Invalid parameters"}), { status: 400 });
    }

    // Отправка уведомления
    if (url.pathname === "/notify") {
      if (request.method !== "POST") return new Response(JSON.stringify({error: "Method Not Allowed"}), { status: 405 });
      try {
        const body = await request.json();
        const deviceId = body.device_id;
        const message = body.message;

        if (deviceId && message) {
          const deviceDataStr = await env.DB.get(`device:${deviceId}`);
          if (deviceDataStr) {
            const deviceData = JSON.parse(deviceDataStr);
            await sendTg(deviceData.chatId, message);
            return new Response(JSON.stringify({success: true}), { status: 200, headers: { "Content-Type": "application/json" } });
          }
        }
      } catch (e) {
        return new Response(JSON.stringify({error: "Bad request"}), { status: 400 });
      }
      return new Response(JSON.stringify({error: "Not linked"}), { status: 404 });
    }

    return new Response("GameAlerter Cloud API is running! V2 (Device IDs with Cooldown logic)");
  }
};
