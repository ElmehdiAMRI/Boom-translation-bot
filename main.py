import os
import discord
from discord.ext import commands, tasks
import asyncio
from typing import Dict, Set, Optional, List, Tuple
import aiohttp
import json
from collections import defaultdict
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from enum import Enum
import pickle
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TranslationBot')

# ==================== Configuration ====================

class TranslationMode(Enum):
    ROLE_BASED = "role"
    REACTION = "reaction"
    AUTO_DETECT = "auto"
    CHANNEL_SPECIFIC = "channel"
    DM = "dm"

@dataclass
class LanguageConfig:
    code: str
    name: str
    flag: str
    deepl_code: str
    azure_code: str
    google_code: str

# Comprehensive language support
LANGUAGES = {
    "en": LanguageConfig("en", "English", "🇬🇧", "EN", "en", "en"),
    "es": LanguageConfig("es", "Spanish", "🇪🇸", "ES", "es", "es"),
    "fr": LanguageConfig("fr", "French", "🇫🇷", "FR", "fr", "fr"),
    "de": LanguageConfig("de", "German", "🇩🇪", "DE", "de", "de"),
    "it": LanguageConfig("it", "Italian", "🇮🇹", "IT", "it", "it"),
    "pt": LanguageConfig("pt", "Portuguese", "🇵🇹", "PT-PT", "pt", "pt"),
    "ru": LanguageConfig("ru", "Russian", "🇷🇺", "RU", "ru", "ru"),
    "ja": LanguageConfig("ja", "Japanese", "🇯🇵", "JA", "ja", "ja"),
    "ko": LanguageConfig("ko", "Korean", "🇰🇷", "KO", "ko", "ko"),
    "zh": LanguageConfig("zh", "Chinese", "🇨🇳", "ZH", "zh-Hans", "zh-CN"),
    "ar": LanguageConfig("ar", "Arabic", "🇸🇦", "AR", "ar", "ar"),
    "hi": LanguageConfig("hi", "Hindi", "🇮🇳", "HI", "hi", "hi"),
    "tr": LanguageConfig("tr", "Turkish", "🇹🇷", "TR", "tr", "tr"),
    "pl": LanguageConfig("pl", "Polish", "🇵🇱", "PL", "pl", "pl"),
    "nl": LanguageConfig("nl", "Dutch", "🇳🇱", "NL", "nl", "nl"),
    "sv": LanguageConfig("sv", "Swedish", "🇸🇪", "SV", "sv", "sv"),
    "da": LanguageConfig("da", "Danish", "🇩🇰", "DA", "da", "da"),
    "no": LanguageConfig("no", "Norwegian", "🇳🇴", "NB", "nb", "no"),
    "fi": LanguageConfig("fi", "Finnish", "🇫🇮", "FI", "fi", "fi"),
    "el": LanguageConfig("el", "Greek", "🇬🇷", "EL", "el", "el"),
    "cs": LanguageConfig("cs", "Czech", "🇨🇿", "CS", "cs", "cs"),
    "hu": LanguageConfig("hu", "Hungarian", "🇭🇺", "HU", "hu", "hu"),
    "ro": LanguageConfig("ro", "Romanian", "🇷🇴", "RO", "ro", "ro"),
    "bg": LanguageConfig("bg", "Bulgarian", "🇧🇬", "BG", "bg", "bg"),
    "uk": LanguageConfig("uk", "Ukrainian", "🇺🇦", "UK", "uk", "uk"),
    "he": LanguageConfig("he", "Hebrew", "🇮🇱", "HE", "he", "he"),
    "th": LanguageConfig("th", "Thai", "🇹🇭", "TH", "th", "th"),
    "vi": LanguageConfig("vi", "Vietnamese", "🇻🇳", "VI", "vi", "vi"),
    "id": LanguageConfig("id", "Indonesian", "🇮🇩", "ID", "id", "id"),
    "ms": LanguageConfig("ms", "Malay", "🇲🇾", "MS", "ms", "ms"),
}

# ==================== Translation Services ====================

class TranslationService:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.cache = {}
        self.rate_limits = defaultdict(lambda: datetime.min)
        
    async def translate(self, text: str, target_lang: str, source_lang: Optional[str] = None) -> Optional[str]:
        """Base translation method to be overridden"""
        raise NotImplementedError

class DeepLTranslator(TranslationService):
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        super().__init__(session)
        self.api_key = api_key
        self.endpoint = "https://api-free.deepl.com/v2/translate"
        
    async def translate(self, text: str, target_lang: str, source_lang: Optional[str] = None) -> Optional[str]:
        cache_key = f"deepl_{text}_{target_lang}_{source_lang}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        lang_config = LANGUAGES.get(target_lang)
        if not lang_config:
            return None
            
        params = {
            "auth_key": self.api_key,
            "text": text,
            "target_lang": lang_config.deepl_code
        }
        
        if source_lang:
            params["source_lang"] = LANGUAGES[source_lang].deepl_code.upper()
            
        try:
            async with self.session.post(self.endpoint, data=params) as response:
                if response.status == 200:
                    data = await response.json()
                    translation = data["translations"][0]["text"]
                    self.cache[cache_key] = translation
                    return translation
        except Exception as e:
            logger.error(f"DeepL translation error: {e}")
        return None

class AzureTranslator(TranslationService):
    def __init__(self, session: aiohttp.ClientSession, api_key: str, region: str):
        super().__init__(session)
        self.api_key = api_key
        self.region = region
        self.endpoint = "https://api.cognitive.microsofttranslator.com/translate"
        
    async def detect_language(self, text: str) -> Optional[str]:
        detect_endpoint = "https://api.cognitive.microsofttranslator.com/detect?api-version=3.0"
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Ocp-Apim-Subscription-Region": self.region,
            "Content-Type": "application/json"
        }
        body = [{"text": text}]
        
        try:
            async with self.session.post(detect_endpoint, headers=headers, json=body) as response:
                if response.status == 200:
                    data = await response.json()
                    detected = data[0]["language"]
                    # Map Azure language codes to our standard codes
                    for code, config in LANGUAGES.items():
                        if config.azure_code == detected:
                            return code
                    return detected
        except Exception as e:
            logger.error(f"Azure language detection error: {e}")
        return None
        
    async def translate(self, text: str, target_lang: str, source_lang: Optional[str] = None) -> Optional[str]:
        cache_key = f"azure_{text}_{target_lang}_{source_lang}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        lang_config = LANGUAGES.get(target_lang)
        if not lang_config:
            return None
            
        params = {
            "api-version": "3.0",
            "to": lang_config.azure_code
        }
        
        if source_lang:
            params["from"] = LANGUAGES[source_lang].azure_code
            
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Ocp-Apim-Subscription-Region": self.region,
            "Content-Type": "application/json"
        }
        
        body = [{"text": text}]
        
        try:
            async with self.session.post(
                self.endpoint, 
                headers=headers, 
                json=body, 
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    translation = data[0]["translations"][0]["text"]
                    self.cache[cache_key] = translation
                    return translation
        except Exception as e:
            logger.error(f"Azure translation error: {e}")
        return None

# ==================== Bot Core ====================

class TranslationBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session: Optional[aiohttp.ClientSession] = None
        self.translators: Dict[str, TranslationService] = {}
        self.user_preferences = defaultdict(dict)
        self.guild_settings = defaultdict(dict)
        self.reaction_messages = {}
        self.translation_stats = defaultdict(int)
        
    async def setup_hook(self):
        """Initialize bot components"""
        self.session = aiohttp.ClientSession()
        
        # Initialize translation services
        if DEEPL_KEY := os.getenv("DEEPL_KEY"):
            self.translators["deepl"] = DeepLTranslator(self.session, DEEPL_KEY)
            
        if (azure_key := os.getenv("AZURE_KEY")) and (azure_region := os.getenv("AZURE_REGION")):
            self.translators["azure"] = AzureTranslator(self.session, azure_key, azure_region)
            
        # Load saved preferences
        self.load_preferences()
        
        # Start background tasks
        self.cleanup_cache.start()
        self.save_preferences_task.start()
        
    async def close(self):
        """Cleanup on bot shutdown"""
        self.save_preferences()
        if self.session:
            await self.session.close()
        await super().close()
        
    def load_preferences(self):
        """Load saved user preferences and guild settings"""
        try:
            if os.path.exists("preferences.pkl"):
                with open("preferences.pkl", "rb") as f:
                    data = pickle.load(f)
                    self.user_preferences = defaultdict(dict, data.get("users", {}))
                    self.guild_settings = defaultdict(dict, data.get("guilds", {}))
        except Exception as e:
            logger.error(f"Error loading preferences: {e}")
            
    def save_preferences(self):
        """Save user preferences and guild settings"""
        try:
            data = {
                "users": dict(self.user_preferences),
                "guilds": dict(self.guild_settings)
            }
            with open("preferences.pkl", "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.error(f"Error saving preferences: {e}")
            
    @tasks.loop(hours=1)
    async def cleanup_cache(self):
        """Clean up old cache entries"""
        for translator in self.translators.values():
            if len(translator.cache) > 1000:
                translator.cache = dict(list(translator.cache.items())[-500:])
                
    @tasks.loop(minutes=30)
    async def save_preferences_task(self):
        """Periodically save preferences"""
        self.save_preferences()

# ==================== Translation Logic ====================

class TranslationHandler:
    def __init__(self, bot: TranslationBot):
        self.bot = bot
        
    async def detect_language(self, text: str) -> Optional[str]:
        """Detect the language of the text"""
        if azure := self.bot.translators.get("azure"):
            return await azure.detect_language(text)
        return None
        
    async def get_user_languages(self, member: discord.Member) -> Set[str]:
        """Get languages for a user based on roles and preferences"""
        languages = set()
        
        # Check user preferences
        if prefs := self.bot.user_preferences.get(member.id):
            if user_langs := prefs.get("languages"):
                languages.update(user_langs)
                
        # Check role-based languages
        for role in member.roles:
            role_name = role.name.lower().strip()
            for lang_code, config in LANGUAGES.items():
                if role_name == config.name.lower() or role_name == lang_code:
                    languages.add(lang_code)
                    
        return languages
        
    async def get_target_users(self, message: discord.Message, source_lang: str) -> Dict[discord.Member, Set[str]]:
        """Get users who need translations and their target languages"""
        guild = message.guild
        if not guild:
            return {}
            
        await guild.chunk()
        target_users = {}
        
        guild_settings = self.bot.guild_settings.get(guild.id, {})
        mode = guild_settings.get("mode", TranslationMode.ROLE_BASED)
        
        for member in message.channel.members:
            if member.bot or member.id == message.author.id:
                continue
                
            if not message.channel.permissions_for(member).read_messages:
                continue
                
            # Check if user is online (if enabled)
            if guild_settings.get("online_only", True):
                if member.status == discord.Status.offline:
                    continue
                    
            user_langs = await self.get_user_languages(member)
            
            if user_langs and source_lang not in user_langs:
                target_users[member] = user_langs
                
        return target_users
        
    async def translate_message(self, text: str, target_lang: str, source_lang: Optional[str] = None) -> Optional[str]:
        """Translate text using available services with fallback"""
        # Try primary service (DeepL)
        if deepl := self.bot.translators.get("deepl"):
            if translation := await deepl.translate(text, target_lang, source_lang):
                return translation
                
        # Fallback to Azure
        if azure := self.bot.translators.get("azure"):
            if translation := await azure.translate(text, target_lang, source_lang):
                return translation
                
        return None
        
    async def create_translation_embed(self, message: discord.Message, translations: Dict[str, str], source_lang: str) -> discord.Embed:
        """Create a formatted embed for translations"""
        embed = discord.Embed(
            title="📝 Translations",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.avatar.url if message.author.avatar else None
        )
        
        # Add original message
        source_config = LANGUAGES.get(source_lang)
        source_flag = source_config.flag if source_config else "🌍"
        embed.add_field(
            name=f"{source_flag} Original ({source_lang})",
            value=message.content[:1024],
            inline=False
        )
        
        # Add translations
        for lang, translation in translations.items():
            if lang_config := LANGUAGES.get(lang):
                embed.add_field(
                    name=f"{lang_config.flag} {lang_config.name}",
                    value=translation[:1024],
                    inline=False
                )
                
        embed.set_footer(text="React with a flag to get translation in DM")
        return embed

# ==================== Bot Commands ====================

class TranslationCommands(commands.Cog):
    def __init__(self, bot: TranslationBot):
        self.bot = bot
        self.handler = TranslationHandler(bot)
        
    @commands.command(name="translate", aliases=["tr"])
    async def translate_command(self, ctx: commands.Context, target_lang: str, *, text: str):
        """Manually translate text to a specific language"""
        if target_lang not in LANGUAGES:
            langs = ", ".join(LANGUAGES.keys())
            await ctx.send(f"❌ Invalid language code. Available: {langs}")
            return
            
        translation = await self.handler.translate_message(text, target_lang)
        if translation:
            lang_config = LANGUAGES[target_lang]
            embed = discord.Embed(
                title=f"{lang_config.flag} Translation to {lang_config.name}",
                description=translation,
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Translation failed. Please try again later.")
            
    @commands.command(name="languages", aliases=["langs"])
    async def list_languages(self, ctx: commands.Context):
        """List all supported languages"""
        embed = discord.Embed(
            title="🌍 Supported Languages",
            color=discord.Color.blue()
        )
        
        langs_list = []
        for code, config in LANGUAGES.items():
            langs_list.append(f"{config.flag} **{config.name}** (`{code}`)")
            
        # Split into columns
        mid = len(langs_list) // 2
        embed.add_field(name="Languages A-M", value="\n".join(langs_list[:mid]), inline=True)
        embed.add_field(name="Languages N-Z", value="\n".join(langs_list[mid:]), inline=True)
        
        await ctx.send(embed=embed)
        
    @commands.command(name="setlang", aliases=["mylang"])
    async def set_user_language(self, ctx: commands.Context, *languages: str):
        """Set your preferred languages"""
        valid_langs = [lang for lang in languages if lang in LANGUAGES]
        
        if not valid_langs:
            await ctx.send("❌ No valid language codes provided.")
            return
            
        self.bot.user_preferences[ctx.author.id]["languages"] = valid_langs
        
        lang_names = [f"{LANGUAGES[lang].flag} {LANGUAGES[lang].name}" for lang in valid_langs]
        await ctx.send(f"✅ Your languages set to: {', '.join(lang_names)}")
        
    @commands.group(name="config", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_group(self, ctx: commands.Context):
        """Server configuration commands"""
        embed = discord.Embed(
            title="⚙️ Server Configuration",
            description="Use subcommands to configure translation settings",
            color=discord.Color.blue()
        )
        
        settings = self.bot.guild_settings.get(ctx.guild.id, {})
        
        embed.add_field(
            name="Current Settings",
            value=f"""
            **Mode:** {settings.get('mode', TranslationMode.ROLE_BASED).value}
            **Online Only:** {settings.get('online_only', True)}
            **Auto Translate:** {settings.get('auto_translate', True)}
            **Flag Reactions:** {settings.get('flag_reactions', True)}
            """,
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    @config_group.command(name="mode")
    @commands.has_permissions(administrator=True)
    async def config_mode(self, ctx: commands.Context, mode: str):
        """Set translation mode (role/reaction/auto/channel/dm)"""
        try:
            mode_enum = TranslationMode(mode)
            self.bot.guild_settings[ctx.guild.id]["mode"] = mode_enum
            await ctx.send(f"✅ Translation mode set to: {mode}")
        except ValueError:
            await ctx.send("❌ Invalid mode. Choose: role/reaction/auto/channel/dm")
            
    @config_group.command(name="autotranslate")
    @commands.has_permissions(administrator=True)
    async def config_auto(self, ctx: commands.Context, enabled: bool):
        """Enable/disable automatic translation"""
        self.bot.guild_settings[ctx.guild.id]["auto_translate"] = enabled
        await ctx.send(f"✅ Auto-translation {'enabled' if enabled else 'disabled'}")
        
    @config_group.command(name="flagreactions")
    @commands.has_permissions(administrator=True)
    async def config_flags(self, ctx: commands.Context, enabled: bool):
        """Enable/disable flag reactions for translations"""
        self.bot.guild_settings[ctx.guild.id]["flag_reactions"] = enabled
        await ctx.send(f"✅ Flag reactions {'enabled' if enabled else 'disabled'}")
        
    @commands.command(name="stats")
    async def translation_stats(self, ctx: commands.Context):
        """Show translation statistics"""
        embed = discord.Embed(
            title="📊 Translation Statistics",
            color=discord.Color.gold()
        )
        
        total = sum(self.bot.translation_stats.values())
        embed.add_field(name="Total Translations", value=str(total), inline=False)
        
        if self.bot.translation_stats:
            top_langs = sorted(self.bot.translation_stats.items(), key=lambda x: x[1], reverse=True)[:5]
            langs_text = "\n".join([f"{LANGUAGES[lang].flag} {LANGUAGES[lang].name}: {count}" 
                                   for lang, count in top_langs if lang in LANGUAGES])
            embed.add_field(name="Top Languages", value=langs_text or "None", inline=False)
            
        await ctx.send(embed=embed)

# ==================== Event Handlers ====================

class TranslationEvents(commands.Cog):
    def __init__(self, bot: TranslationBot):
        self.bot = bot
        self.handler = TranslationHandler(bot)
        self.processing = set()
        
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle automatic message translation"""
        if message.author.bot or not message.content.strip():
            return
            
        if not message.guild:
            return
            
        # Check if auto-translate is enabled
        guild_settings = self.bot.guild_settings.get(message.guild.id, {})
        if not guild_settings.get("auto_translate", True):
            return
            
        # Avoid processing same message twice
        if message.id in self.processing:
            return
        self.processing.add(message.id)
        
        try:
            # Detect source language
            source_lang = await self.handler.detect_language(message.content)
            if not source_lang:
                return
                
            logger.info(f"Detected language: {source_lang} for message from {message.author}")
            
            # Get target users and their languages
            target_users = await self.handler.get_target_users(message, source_lang)
            if not target_users:
                return
                
            # Collect unique target languages
            target_langs = set()
            for user_langs in target_users.values():
                target_langs.update(user_langs)
                
            # Translate to each language
            translations = {}
            for lang in target_langs:
                if lang != source_lang:
                    if translation := await self.handler.translate_message(message.content, lang, source_lang):
                        translations[lang] = translation
                        self.bot.translation_stats[lang] += 1
                        
            if translations:
                # Create translation embed
                embed = await self.handler.create_translation_embed(message, translations, source_lang)
                msg = await message.reply(embed=embed, mention_author=False)
                
                # Add flag reactions if enabled
                if guild_settings.get("flag_reactions", True):
                    self.bot.reaction_messages[msg.id] = {
                        "original": message,
                        "translations": translations,
                        "source_lang": source_lang
                    }
                    
                    # Add reaction for each translated language
                    for lang in translations.keys():
                        if lang_config := LANGUAGES.get(lang):
                            try:
                                await msg.add_reaction(lang_config.flag)
                            except:
                                pass
                                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
        finally:
            # Remove from processing after a delay
            await asyncio.sleep(5)
            self.processing.discard(message.id)
            
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle flag reactions for DM translations"""
        if payload.user_id == self.bot.user.id:
            return
            
        if payload.message_id not in self.bot.reaction_messages:
            return
            
        msg_data = self.bot.reaction_messages[payload.message_id]
        
        # Find language for this flag
        target_lang = None
        for lang, config in LANGUAGES.items():
            if str(payload.emoji) == config.flag:
                target_lang = lang
                break
                
        if not target_lang:
            return
            
        # Get the translation
        translation = msg_data["translations"].get(target_lang)
        if not translation:
            # Translate on demand if not available
            translation = await self.handler.translate_message(
                msg_data["original"].content, 
                target_lang, 
                msg_data["source_lang"]
            )
            
        if translation:
            # Send DM to user
            try:
                user = self.bot.get_user(payload.user_id)
                if user:
                    embed = discord.Embed(
                        title=f"{LANGUAGES[target_lang].flag} Translation",
                        description=translation,
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="Original Message",
                        value=f"[Jump to message]({msg_data['original'].jump_url})",
                        inline=False
                    )
                    await user.send(embed=embed)
            except discord.Forbidden:
                pass

# ==================== Main Bot Setup ====================

def main():
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Bot configuration
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.reactions = True
    intents.presences = True
    
    bot = TranslationBot(
        command_prefix=commands.when_mentioned_or("!", "t!"),
        intents=intents,
        help_command=commands.DefaultHelpCommand(
            no_category="Translation Commands"
        )
    )
    
    @bot.event
    async def on_ready():
        logger.info(f"✅ {bot.user} is online!")
        logger.info(f"📡 Connected to {len(bot.guilds)} servers")
        
        # Set status
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(LANGUAGES)} languages | !help"
            )
        )
    
    async def setup():
        """Setup bot cogs"""
        await bot.add_cog(TranslationCommands(bot))
        await bot.add_cog(TranslationEvents(bot))
    
    # Run setup before starting
    asyncio.run(setup())
    
    # Keep alive for web hosting
    if os.getenv("USE_KEEP_ALIVE", "false").lower() == "true":
        from keep_alive import keep_alive
        keep_alive()
    
    # Start bot
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("❌ DISCORD_TOKEN not found in environment variables!")
        return
        
    bot.run(token)

if __name__ == "__main__":
    main()
