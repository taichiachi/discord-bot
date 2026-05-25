import discord
import asyncio
import os
import logging
from aiohttp import web

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
TOKEN = os.environ.get("DISCORD_TOKEN")
PORT = int(os.environ.get("PORT", 8080))

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.message_content = True
intents.messages = True

client = discord.Client(intents=intents)
voice_client = None

# ── Web server to keep Render alive ──
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")

# ── Keep alive loop ──
async def keep_alive_loop():
    await client.wait_until_ready()
    await asyncio.sleep(5)

    while not client.is_closed():
        try:
            if voice_client and not voice_client.is_connected():
                logger.warning("Disconnected! Reconnecting...")
                await voice_client.channel.connect()
        except Exception as e:
            logger.error(f"Error in keep_alive_loop: {e}")
        await asyncio.sleep(30)

# ── Events ──
@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")
    print(f"✅ Bot is online: {client.user}")

@client.event
async def on_message(message):
    global voice_client

    if message.author == client.user:
        return

    # !join — join the VC of the user who typed the command
    if message.content.lower() == "!join":
        if message.author.voice is None:
            await message.channel.send("❌ You are not in a voice channel!")
            return

        channel = message.author.voice.channel

        try:
            if voice_client and voice_client.is_connected():
                await voice_client.move_to(channel)
                await message.channel.send(f"✅ Moved to **{channel.name}**!")
            else:
                voice_client = await channel.connect()
                await message.channel.send(f"✅ Joined **{channel.name}**!")
        except Exception as e:
            await message.channel.send(f"❌ Error: {e}")
            logger.error(f"Error on !join: {e}")

    # !leave — leave the VC
    elif message.content.lower() == "!leave":
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
            voice_client = None
            await message.channel.send("👋 Left the voice channel!")
        else:
            await message.channel.send("❌ I'm not in any voice channel!")

    # !status — check if connected
    elif message.content.lower() == "!status":
        if voice_client and voice_client.is_connected():
            await message.channel.send(f"✅ Currently in **{voice_client.channel.name}**!")
        else:
            await message.channel.send("❌ I'm not in any voice channel.")

@client.event
async def on_voice_state_update(member, before, after):
    """Auto-reconnect if the bot gets kicked."""
    global voice_client

    if member == client.user:
        if before.channel is not None and after.channel is None:
            logger.warning("Bot was kicked/disconnected! Reconnecting...")
            await asyncio.sleep(3)
            try:
                voice_client = await before.channel.connect()
                logger.info(f"Reconnected to {before.channel.name}")
            except Exception as e:
                logger.error(f"Failed to reconnect: {e}")

async def main():
    await start_web_server()
    asyncio.ensure_future(keep_alive_loop())
    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
