#!/usr/bin/env python3
"""
Discord Translation Bot - Oracle Cloud Optimized Version
Optimized for Oracle Cloud Free Tier VPS (4 ARM cores, 24GB RAM)
"""

import os
import sys
import discord
from discord.ext import commands, tasks
import asyncio
from typing import Dict, Set, Optional
import aiohttp
from collections import defaultdict
from datetime import datetime
import logging
from dataclasses import dataclass
from enum import Enum

# ==================== Oracle Cloud Optimizations ====================

# Set up proper logging for systemd
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # For systemd journal
        logging.FileHandler('/home/ubuntu/discord-bot/bot.log')  # File logging
    ]
)
logger = logging.getLogger('TranslationBot')

# Performance settings for Oracle's ARM processors
# Oracle gives us 4 OCPU ARM cores - let's use them efficiently
CONCURRENT_TRANSLATIONS = 10  # Can handle many concurrent translations
CACHE_SIZE = 5000  # Larger cache since we have 24GB RAM
RATE_LIMIT_WINDOW = 60  # seconds

# ==================== Simplified Configuration ====================

@dataclass
class LanguageConfig:
    code: str
    name: str
    flag: str
    deepl_code: str
    azure_code: str

# Essential languages (add more as needed)
LANGUAGES = {
    "en": LanguageConfig("en", "English", "🇬🇧", "EN", "en"),
    "es": LanguageConfig("es", "Spanish", "🇪🇸", "ES", "es"),
    "fr": LanguageConfig("fr", "French", "🇫🇷", "FR", "fr"),
    "de": LanguageConfig("de", "German", "🇩🇪", "DE", "de"),
    "it": LanguageConfig("it", "Italian", "🇮🇹", "IT", "it"),
    "pt": LanguageConfig("pt", "Portuguese", "🇵🇹", "PT-PT", "pt"),
    "ru": LanguageConfig("ru", "Russian", "🇷🇺", "RU", "ru"),
    "ar": LanguageConfig("ar", "Arabic", "🇸🇦", "AR", "ar"),
    "ja": LanguageConfig("ja", "Japanese", "🇯🇵", "JA", "ja"),
    "zh": LanguageConfig("zh", "Chinese", "🇨🇳", "ZH", "zh-Hans"),
    "nl": LanguageConfig("nl", "Dutch", "🇳🇱", "NL", "nl"),
    "uk": LanguageConfig("uk", "Ukrainian", "🇺🇦", "UK", "uk"),
    "pl": LanguageConfig("pl", "Polish", "🇵🇱", "PL", "pl"),
    "tr": LanguageConfig("tr", "Turkish", "🇹🇷", "TR", "tr"),
}

# ==================== Translation Services ====================

class TranslationService:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.cache = {}
        self.semaphore = asyncio.Semaphore(CONCURRENT_TRANSLATIONS)
        
    async def translate(self, text: str, target_lang: str, source_lang: Optional[str] = None) -> Optional[str]:
        async with self.semaphore:
            cache_key = f"{text[:50]}_{target_lang}_{source_lang}"
            if cache_key in self.cache:
                logger.debug(f"Cache hit for {cache_key}")
                return self.cache[cache_key]
            
            result = await self._do_translate(text, target_lang, source_lang)
            
            if result and len(self.cache) < CACHE_SIZE:
                self.cache[cache_key] = result
                
            return result
    
    async def _do_translate(self, text: str, target_lang: str, source_lang: Optional[str] = None) -> Optional[str]:
        raise NotImplementedError

class DeepLTranslator(TranslationService):
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        super().__init__(session)
        self.api_key = api_key
        self.endpoint = "https://api-free.deepl.com/v2/translate"
        
    async def _do_translate(self, text: str, target_lang: str, source_lang: Optional[str] = None) -> Optional[str]:
        lang_config = LANGUAGES.get(target_lang)
        if not lang_config:
            return None
            
        params = {
            "auth_key": self.api_key,
            "text": text,
            "target_lang": lang_config.deepl_code
        }
        
        try:
            async with self.session.post(self.endpoint, data=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["translations"][0]["text"]
                else:
                    logger.warning(f"DeepL returned status {response.status}")
        except asyncio.TimeoutError:
            logger.error("DeepL translation timeout")
        except Exception as e:
            logger.error(f"DeepL error: {e}")
        return None

class AzureTranslator(TranslationService):
    def __init__(self, session: aiohttp.ClientSession, api_key: str, region: str):
        super().__init__(session)
        self.api_key = api_key
        self.region = region
        
    async def detect_language(self, text: str) -> Optional[str]:
        """Detect language with caching"""
        cache_key = f"detect_{text[:50]}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        detect_endpoint = "https://api.cognitive.microsofttranslator.com/detect?api-version=3.0"
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Ocp-Apim-Subscription-Region": self.region,
            "Content-Type": "application/json"
        }
        
        try:
            async with self.session.post(
                detect_endpoint, 
                headers=headers, 
                json=[{"text": text}],
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    detected = data[0]["language"]
                    
                    # Map to our language codes
                    for code, config in LANGUAGES.items():
                        if config.azure_code == detected:
                            self.cache[cache_key] = code
                            return code
                    return detected
        except Exception as e:
            logger.error(f"Language detection error: {e}")
        return None
        
    async def _do_translate(self, text: str, target_lang: str, source_lang: Optional[str] = None) -> Optional[str]:
        lang_config = LANGUAGES.get(target_lang)
        if not lang_config:
            return None
            
        endpoint = "https://api.cognitive.microsofttranslator.com/translate"
        params = {
            "api-version": "3.0",
            "to": lang_config.azure_code
        }
        
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Ocp-Apim-Subscription-Region": self.region,
            "Content-Type": "application/json"
        }
        
        try:
            async with self.session.post(
                endpoint,
                headers=headers,
                json=[{"text": text}],
                params=params,
                timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data[0]["translations"][0]["text"]
        except Exception as e:
            logger.error(f"Azure translation error: {e}")
        return None

# ==================== Optimized Bot Core ====================

class TranslationBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session: Optional[aiohttp.ClientSession] = None
        self.translators: Dict[str, TranslationService] = {}
        self.translation_stats = defaultdict(int)
        self.processing = set()  # Prevent duplicate processing
        
    async def setup_hook(self):
        """Initialize bot components"""
        # Create optimized aiohttp session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool limit
            limit_per_host=30,  # Per-host limit
            ttl_dns_cache=300  # DNS cache
        )
        self.session = aiohttp.ClientSession(connector=connector)
        
        # Initialize translation services
        if deepl_key := os.getenv("DEEPL_KEY"):
            self.translators["deepl"] = DeepLTranslator(self.session, deepl_key)
            logger.info("✅ DeepL translator initialized")
            
        if (azure_key := os.getenv("AZURE_KEY")) and (azure_region := os.getenv("AZURE_REGION")):
            self.translators["azure"] = AzureTranslator(self.session, azure_key, azure_region)
            logger.info("✅ Azure translator initialized")
            
        if not self.translators:
            logger.warning("⚠️ No translation services configured!")
            
        # Start cleanup task
        self.cleanup_cache.start()
        
    async def close(self):
        """Cleanup on shutdown"""
        self.cleanup_cache.cancel()
        if self.session:
            await self.session.close()
        await super().close()
        
    @tasks.loop(hours=1)
    async def cleanup_cache(self):
        """Periodically clean cache"""
        for translator in self.translators.values():
            if len(translator.cache) > CACHE_SIZE:
                # Keep most recent entries
                translator.cache = dict(list(translator.cache.items())[-CACHE_SIZE//2:])
                logger.info(f"Cache cleaned, kept {len(translator.cache)} entries")

    async def on_ready(self):
        """Bot ready event"""
        logger.info(f"✅ {self.user} is online!")
        logger.info(f"📡 Connected to {len(self.guilds)} servers")
        logger.info(f"💾 Running on Oracle Cloud with {CONCURRENT_TRANSLATIONS} concurrent workers")
        
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(LANGUAGES)} languages | !help"
            )
        )

    async def on_message(self, message: discord.Message):
        """Process messages for translation"""
        # Skip if bot, empty, or already processing
        if message.author.bot or not message.content or message.id in self.processing:
            return
            
        # Add to processing set
        self.processing.add(message.id)
        
        try:
            # Process commands first
            await self.process_commands(message)
            
            # Auto-translate logic
            if message.guild:  # Only in servers
                await self.auto_translate(message)
                
        finally:
            # Remove from processing after delay
            await asyncio.sleep(2)
            self.processing.discard(message.id)
            
    async def auto_translate(self, message: discord.Message):
        """Auto-translate messages"""
        try:
            # Detect language
            if azure := self.translators.get("azure"):
                source_lang = await azure.detect_language(message.content)
                
                if not source_lang:
                    return
                    
                # Get users with different language roles
                target_langs = set()
                for member in message.channel.members:
                    if member.bot or member == message.author:
                        continue
                        
                    # Check member roles for languages
                    for role in member.roles:
                        role_lower = role.name.lower()
                        for lang_code, config in LANGUAGES.items():
                            if role_lower == config.name.lower() or role_lower == lang_code:
                                if lang_code != source_lang:
                                    target_langs.add(lang_code)
                                    
                if target_langs:
                    # Translate to needed languages
                    translations = {}
                    translation_tasks = []
                    
                    for lang in target_langs:
                        # Try DeepL first, then Azure
                        translator = self.translators.get("deepl") or self.translators.get("azure")
                        if translator:
                            task = translator.translate(message.content, lang, source_lang)
                            translation_tasks.append((lang, task))
                            
                    # Gather all translations concurrently
                    for lang, task in translation_tasks:
                        try:
                            result = await asyncio.wait_for(task, timeout=10)
                            if result:
                                translations[lang] = result
                                self.translation_stats[lang] += 1
                        except asyncio.TimeoutError:
                            logger.warning(f"Translation timeout for {lang}")
                            
                    # Send translations if any
                    if translations:
                        embed = discord.Embed(
                            title="📝 Translations",
                            color=discord.Color.blue(),
                            timestamp=datetime.utcnow()
                        )
                        
                        # Add original
                        source_config = LANGUAGES.get(source_lang)
                        if source_config:
                            embed.add_field(
                                name=f"{source_config.flag} Original ({source_lang})",
                                value=message.content[:1024],
                                inline=False
                            )
                            
                        # Add translations
                        for lang, text in translations.items():
                            if config := LANGUAGES.get(lang):
                                embed.add_field(
                                    name=f"{config.flag} {config.name}",
                                    value=text[:1024],
                                    inline=False
                                )
                                
                        await message.reply(embed=embed, mention_author=False)
                        
        except Exception as e:
            logger.error(f"Auto-translate error: {e}")

# ==================== Basic Commands ====================

@commands.command(name="translate", aliases=["tr"])
async def translate_command(ctx: commands.Context, target_lang: str, *, text: str):
    """Translate text to a specific language"""
    bot = ctx.bot
    
    if target_lang not in LANGUAGES:
        await ctx.send(f"❌ Invalid language. Available: {', '.join(LANGUAGES.keys())}")
        return
        
    # Get translator
    translator = bot.translators.get("deepl") or bot.translators.get("azure")
    if not translator:
        await ctx.send("❌ No translation service available")
        return
        
    # Translate
    async with ctx.typing():
        translation = await translator.translate(text, target_lang)
        
    if translation:
        config = LANGUAGES[target_lang]
        embed = discord.Embed(
            title=f"{config.flag} Translation to {config.name}",
            description=translation,
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Translation failed")

@commands.command(name="languages", aliases=["langs"])
async def list_languages(ctx: commands.Context):
    """List supported languages"""
    embed = discord.Embed(
        title="🌍 Supported Languages",
        description="\n".join([f"{c.flag} **{c.name}** (`{code}`)" 
                              for code, c in LANGUAGES.items()]),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@commands.command(name="stats")
async def stats_command(ctx: commands.Context):
    """Show translation statistics"""
    bot = ctx.bot
    total = sum(bot.translation_stats.values())
    
    embed = discord.Embed(
        title="📊 Translation Statistics",
        description=f"**Total Translations:** {total}",
        color=discord.Color.gold()
    )
    
    if bot.translation_stats:
        top = sorted(bot.translation_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        stats_text = "\n".join([f"{LANGUAGES[l].flag} {LANGUAGES[l].name}: {c}" 
                                for l, c in top if l in LANGUAGES])
        embed.add_field(name="Top Languages", value=stats_text or "None")
        
    # System stats
    embed.add_field(
        name="System",
        value=f"Cache Size: {sum(len(t.cache) for t in bot.translators.values())} entries\n"
              f"Active Translators: {', '.join(bot.translators.keys())}",
        inline=False
    )
    
    await ctx.send(embed=embed)

# ==================== Main Entry Point ====================

def main():
    """Main entry point"""
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check token
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("❌ DISCORD_TOKEN not found!")
        sys.exit(1)
        
    # Configure intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    
    # Create bot
    bot = TranslationBot(
        command_prefix=commands.when_mentioned_or("!", "t!"),
        intents=intents,
        help_command=commands.DefaultHelpCommand()
    )
    
    # Add commands
    bot.add_command(translate_command)
    bot.add_command(list_languages)
    bot.add_command(stats_command)
    
    # Run bot
    try:
        logger.info("🚀 Starting Discord Translation Bot on Oracle Cloud...")
        bot.run(token)
    except KeyboardInterrupt:
        logger.info("⏹️ Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
