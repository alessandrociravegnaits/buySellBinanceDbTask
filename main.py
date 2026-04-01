"""Entry point applicazione: avvia il bot Telegram in polling continuo."""

import logging

from telegram_bot import build_bot_from_env


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    build_bot_from_env().run()


if __name__ == "__main__":
    main()
