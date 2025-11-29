from bot import Bot

if __name__ == "__main__":
    try:
        app = Bot()
        app.run()
    except Exception as e:
        print("Bot crashed:", e)
