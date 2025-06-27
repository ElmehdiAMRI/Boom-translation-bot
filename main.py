import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import requests
from keep_alive import keep_alive

# Load secrets
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DEEPL_KEY = os.getenv("DEEPL_KEY")
AZURE_KEY = os.getenv("AZURE_KEY")
AZURE_REGION = os.getenv("AZURE_REGION")

# Discord bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Language role map
ROLE_LANGUAGES = {
    "english": "en",
    "arabic": "ar",
    "french": "fr",
    "german": "de",
    "russian": "ru",
    "dutch": "nl",
    "ukrainian": "uk",
    "spanish": "es",
    "italian": "it"
}

# Language flag emojis
LANG_FLAGS = {
    "en": "🇬🇧", "ar": "🇸🇦", "fr": "🇫🇷", "de": "🇩🇪",
    "ru": "🇷🇺", "nl": "🇳🇱", "uk": "🇺🇦",
    "es": "🇪🇸", "it": "🇮🇹"
}

# Language detection using Azure
def detect_language_with_azure(text):
    endpoint = f"https://api.cognitive.microsofttranslator.com/detect?api-version=3.0"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Ocp-Apim-Subscription-Region": AZURE_REGION,
        "Content-Type": "application/json"
    }
    body = [{"text": text}]
    try:
        response = requests.post(endpoint, headers=headers, json=body)
        response.raise_for_status()
        return response.json()[0]["language"]
    except Exception as e:
        print(f"❌ Azure language detection failed: {e}")
        return None

# Translation using DeepL
def translate_with_deepl(text, to_lang):
    deepl_lang = to_lang.upper()
    endpoint = "https://api-free.deepl.com/v2/translate"
    params = {
        "auth_key": DEEPL_KEY,
        "text": text,
        "target_lang": deepl_lang
    }
    try:
        response = requests.post(endpoint, data=params)
        response.raise_for_status()
        return response.json()["translations"][0]["text"]
    except Exception as e:
        print(f"⚠️ DeepL failed for {to_lang}: {e}")
        return None

# Determine which online users need translation
async def get_target_languages(message, detected_lang):
    guild = message.guild
    channel = message.channel
    sender_id = message.author.id
    await guild.chunk()

    target_languages = set()

    for member in guild.members:
        if member.bot or member.id == sender_id:
            continue
        if not channel.permissions_for(member).read_messages:
            continue
        status = str(member.status).lower()
        raw = getattr(member, "raw_status", None)
        is_online = status in ["online", "idle", "dnd"] or (raw and raw != "offline")
        if not is_online:
            continue

        member_langs = set()
        for role in member.roles:
            role_name = role.name.lower().strip()
            if role_name in ROLE_LANGUAGES:
                lang_code = ROLE_LANGUAGES[role_name]
                member_langs.add(lang_code)

        if member_langs and detected_lang not in member_langs:
            target_languages.update(member_langs)

    return target_languages

# Send translated replies
async def send_translations(message, detected_lang, target_langs):
    translations = []
    for lang in target_langs:
        translated = translate_with_deepl(message.content, lang)
        if translated:
            flag = LANG_FLAGS.get(lang, "")
            translations.append(f"{flag} **{translated}**\n*translated from `{detected_lang}` using DeepL*")
    if translations:
        await message.reply("\n\n".join(translations), mention_author=False)

# Bot startup
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

# Handle messages
@bot.event
async def on_message(message):
    if message.author.bot or not message.content.strip():
        return

    print(f"\n📨 Message from {message.author.display_name}: '{message.content}'")
    detected_lang = detect_language_with_azure(message.content)
    if not detected_lang:
        return

    print(f"✅ Detected language: {detected_lang}")
    target_langs = await get_target_languages(message, detected_lang)
    print(f"🎯 Translations needed: {target_langs}")

    if target_langs:
        await send_translations(message, detected_lang, target_langs)

    await bot.process_commands(message)

# Keep bot alive
keep_alive()

# Start bot
bot.run(DISCORD_TOKEN)
