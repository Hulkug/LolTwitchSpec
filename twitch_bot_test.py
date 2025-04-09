import os
from twitchio.ext import commands
from dotenv import load_dotenv

load_dotenv()

TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL")
TWITCH_NICK = os.getenv("TWITCH_NICK")
TWITCH_TOKEN = os.getenv("TWITCH_TOKEN")


class Bot(commands.Bot):

    def __init__(self):
        super().__init__(
            token=TWITCH_TOKEN,
            prefix="!",
            initial_channels=[TWITCH_CHANNEL]
        )

    async def event_ready(self):
        print(f"✅ Bot connecté en tant que {self.nick}")
        channel = self.get_channel(TWITCH_CHANNEL)
        if channel:
            await channel.send("Bot connecté ! 🎉")

    async def event_message(self, message):
        print(f"[{message.author.name}] {message.content}")
        await self.handle_commands(message)


if __name__ == "__main__":
    bot = Bot()
    bot.run()
