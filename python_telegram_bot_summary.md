**python-telegram-bot — Punti chiave (sintesi)**

- **Panoramica:** libreria Python per Telegram Bot API, supporta API asincrona moderna (v20+), `Application`/`ApplicationBuilder`.

- **Installazione:**
  - `pip install python-telegram-bot` (o versione specifica es. `==22.5`).

- **Costruzione dell'app:**
  - `application = Application.builder().token("YOUR_BOT_TOKEN").build()`
  - Registrare handler: `application.add_handler(CommandHandler("start", start))`.

- **Handler e callback:**
  - Callback asincroni: `async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): ...`
  - Tipi comuni: `CommandHandler`, `MessageHandler`, `CallbackQueryHandler`, `ConversationHandler`.

- **Avvio:**
  - Polling (dev e semplici deploy): `application.run_polling()`
  - Webhook (produzione): `application.run_webhook(listen=..., port=..., webhook_url=..., cert=..., key=...)`

- **Persistenza:**
  - `PicklePersistence` o altre persistence implementazioni: `Application.builder().persistence(my_persistence).build()`
  - Salva `user_data`, `chat_data`, `bot_data` automaticamente.

- **Lifecycle e cleanup:**
  - Pattern `async with application: application.start(); application.stop()` per init/cleanup puliti.

- **Configurazioni utili:**
  - `allowed_updates` per limitare tipi di update; logging configurabile; gestire `httpx` log.

- **Best practices:**
  - Usare handler asincroni per evitare blocchi.
  - Separare logica di business dai callback (testabilità).
  - Proteggere il token (variabili d'ambiente/secret manager).
  - Usare webhook in produzione con HTTPS e `secret_token`.
  - Gestire retry/rate-limit e error handling centralizzato.

- **Nota progetto corrente:**
  - Il bot del repo usa `ApplicationBuilder`, `AUTHORIZED_CHAT_ID` da `.env` e persistenza SQLite.
  - Le impostazioni runtime sono salvate in `bot_settings` e includono anche la soglia BTC di liquidazione automatica (`btc_liquidation_drop_percent`).
  - I riassunti di sessione vengono mantenuti in `.copilot-memory/` alla root del progetto, in file Markdown per argomento.

- **Esempio rapido:**
```python
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Ciao!")

def main() -> None:
    application = Application.builder().token("YOUR_BOT_TOKEN").build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

if __name__ == "__main__":
    main()
```

- **Risorse utili:**
  - Documentazione ufficiale: https://docs.python-telegram-bot.org/
  - Wiki/Examples: https://github.com/python-telegram-bot/python-telegram-bot/wiki

