import discord

class BaseBot(discord.Bot):
    async def on_ready(self):
        print("Logged in as " + self.user.name)