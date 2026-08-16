import os
import json
import random
import time
import asyncio
import traceback
import requests
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

import config
from keep_alive import keep_alive

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
JSONBIN_API_KEY = os.getenv("JSONBIN_API_KEY")
JSONBIN_BIN_ID = os.getenv("JSONBIN_BIN_ID")

DATA_FILE = "bot_data.json"

# --- PAYLAŞILAN HTTP OTURUMU (her istekte yeni bağlantı açmamak için) ---

http_session: aiohttp.ClientSession | None = None

async def get_http_session() -> aiohttp.ClientSession:
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()
    return http_session

DEFAULT_DATA = {
    "welcome_channel_id": config.DEFAULT_WELCOME_CHANNEL_ID,
    "welcome_message": "{user} sunucumuza katıldı,Hoşgeldin!!",
    "welcome_gif": "https://tenor.com/bsXRE.gif",
    "leave_message": "{user} aramızdan ayrıldı...Helvası neyli olsun bu arada-",
    "leave_gif": "https://tenor.com/betLZ.gif",
    "bot_status": "Heavenly Court 🐉",
    "auto_user_role": "~ Oathbound",
    "auto_bot_role": "~ Minions",
    "custom_responses": {},
    
    # KELİME TÜRETMECE OYUNU
    "word_game_channel_id": config.DEFAULT_WORD_GAME_CHANNEL_ID,
    "word_game_last_word": None,
    "word_game_last_user_id": None,
    "word_game_used_words": [],
    "word_game_scores": {},

    # SAYI SAYMACA OYUNU
    "count_game_channel_id": config.DEFAULT_COUNT_GAME_CHANNEL_ID,
    "count_game_current": 1,
    "count_game_last_user_id": None,
    "count_game_high_score": 0,
    "count_game_user_counts": {}
}

INITIAL_WORDS = [
    "tiamat", "ejderha", "anadolu", "efsane", "krallık", "destan", 
    "büyü", "zindan", "kalkan", "kılıç", "zaman", "macera", "hazine"
]

# --- BULUT VERİTABANI (JSONBIN.IO) ENTEGRASYONU ---

def load_from_jsonbin():
    if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
        return None
    try:
        headers = {"X-Master-Key": JSONBIN_API_KEY}
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest"
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            print("🌐 Veriler JSONBin bulut veritabanından yüklendi!")
            return res.json().get("record", {})
    except Exception as e:
        print(f"JSONBin okuma hatası: {e}")
    return None

async def push_to_jsonbin(data):
    if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
        return
    try:
        headers = {
            "X-Master-Key": JSONBIN_API_KEY,
            "Content-Type": "application/json"
        }
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
        session = await get_http_session()
        async with session.put(url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            await resp.read()
        print("☁️ Veriler JSONBin bulut veritabanına kaydedildi!")
    except Exception as e:
        print(f"JSONBin kaydetme hatası: {e}")

# JSONBin'e her oyun hamlesinde değil, art arda gelen hamleler dindikten
# JSONBIN_SAVE_DELAY saniye sonra tek seferde kaydeder (rate limit'e takılmamak için).
JSONBIN_SAVE_DELAY = 5.0
_jsonbin_save_task: asyncio.Task | None = None

async def _delayed_jsonbin_push(data):
    try:
        await asyncio.sleep(JSONBIN_SAVE_DELAY)
        await push_to_jsonbin(data)
    except asyncio.CancelledError:
        pass

def save_to_jsonbin(data):
    global _jsonbin_save_task
    if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
        return
    if _jsonbin_save_task and not _jsonbin_save_task.done():
        _jsonbin_save_task.cancel()
    _jsonbin_save_task = asyncio.create_task(_delayed_jsonbin_push(dict(data)))

def load_data():
    # Önce JSONBin dene, yoksa yerel dosyadan oku
    cloud_data = load_from_jsonbin()
    if cloud_data:
        for k, v in DEFAULT_DATA.items():
            if k not in cloud_data or cloud_data[k] is None:
                cloud_data[k] = v
        return cloud_data

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in DEFAULT_DATA.items():
                    if k not in data or data[k] is None:
                        data[k] = v
                return data
        except Exception as e:
            print(f"Veri yükleme hatası: {e}")
            return dict(DEFAULT_DATA)
    return dict(DEFAULT_DATA)

def save_data(data):
    # Yerel dosyaya yaz
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Veri kaydetme hatası: {e}")

    # JSONBin varsa buluta da gönder
    save_to_jsonbin(data)

bot_data = load_data()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class VassalBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash komutları senkronize edildi.")

    async def close(self):
        global http_session
        if http_session and not http_session.closed:
            await http_session.close()
        await super().close()

bot = VassalBot()

# --- KANAL KONTROLLERİ (KESİN ID VE AD EŞLEŞTİRME) ---

def get_welcome_channel(guild: discord.Guild):
    welcome_id = bot_data.get("welcome_channel_id")
    if welcome_id:
        channel = guild.get_channel(welcome_id)
        if channel:
            return channel
            
    for ch in guild.text_channels:
        ch_name = ch.name.lower()
        if any(k in ch_name for k in ["avlu", "giriş", "giris", "welcome", "hoşgeldin", "hosgeldin"]):
            return ch

    return guild.system_channel or (guild.text_channels[0] if guild.text_channels else None)

def is_word_game_channel(channel: discord.TextChannel) -> bool:
    saved_id = bot_data.get("word_game_channel_id")
    if saved_id:
        return channel.id == saved_id
    return False

def is_count_game_channel(channel: discord.TextChannel) -> bool:
    saved_id = bot_data.get("count_game_channel_id")
    if saved_id:
        return channel.id == saved_id
    return False

# --- TDK KELİME KONTROLÜ ---

# Aynı kelime tekrar sorulduğunda TDK'ya tekrar istek atmamak için önbellek,
# ve art arda gelen isteklerin arasına minimum boşluk koyan basit bir rate limiter.
tdk_word_cache: dict[str, bool] = {}
_tdk_lock: asyncio.Lock | None = None
_tdk_last_request_time = 0.0
TDK_MIN_INTERVAL = 0.5  # gerçek TDK istekleri arasında en az bu kadar saniye bekle

async def is_valid_tdk_word(word: str) -> bool:
    global _tdk_lock, _tdk_last_request_time
    word_clean = word.strip().lower()

    if word_clean in tdk_word_cache:
        return tdk_word_cache[word_clean]

    if _tdk_lock is None:
        _tdk_lock = asyncio.Lock()

    url = f"https://sozluk.gov.tr/gts?ara={word_clean}"
    try:
        async with _tdk_lock:
            wait = TDK_MIN_INTERVAL - (time.monotonic() - _tdk_last_request_time)
            if wait > 0:
                await asyncio.sleep(wait)
            _tdk_last_request_time = time.monotonic()

            session = await get_http_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list) and len(data) > 0 and "error" not in data[0]:
                        tdk_word_cache[word_clean] = True
                        return True
                    elif isinstance(data, dict) and "error" not in data:
                        tdk_word_cache[word_clean] = True
                        return True
    except Exception as e:
        print(f"TDK API Bağlantı Hatası: {e}")
        return len(word_clean) >= 2 and word_clean.isalpha()

    tdk_word_cache[word_clean] = False
    return False

def get_role_by_identifier(guild: discord.Guild, identifier: str | int):
    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
        role = guild.get_role(int(identifier))
        if role:
            return role
    return discord.utils.get(guild.roles, name=str(identifier))

# --- DİNAMİK ROL SEÇİMİ ---

class DynamicRoleSelect(discord.ui.Select):
    def __init__(self, roles_data: list):
        options = []
        for r in roles_data:
            options.append(discord.SelectOption(
                label=r["label"][:100],
                value=str(r["value"]),
                emoji=r.get("emoji", None)
            ))
        if not options:
            options.append(discord.SelectOption(label="Varsayılan Rol", value="none"))

        super().__init__(
            options=options,
            placeholder="Rollerinizi seçin...",
            min_values=1,
            max_values=min(len(options), 25),
            custom_id=f"dyn_select_{random.randint(10000, 99999)}"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            guild = interaction.guild
            user = interaction.user
            if not guild or not isinstance(user, discord.Member):
                return await interaction.response.send_message("Bu işlem sunucuda yapılmalıdır.", ephemeral=True)

            added = []
            removed = []
            not_found = []

            for val in self.values:
                role = get_role_by_identifier(guild, val)
                if role:
                    if role in user.roles:
                        await user.remove_roles(role)
                        removed.append(role.name)
                    else:
                        await user.add_roles(role)
                        added.append(role.name)
                else:
                    not_found.append(str(val))

            msg = []
            if added:
                msg.append(f"✅ Eklenen roller: **{', '.join(added)}**")
            if removed:
                msg.append(f"❌ Kaldırılan roller: **{', '.join(removed)}**")
            if not_found:
                msg.append(f"⚠️ Sunucuda bulunamayan roller: **{', '.join(not_found)}**")
            if not msg:
                msg.append("Rol durumunuz değişmedi.")

            await interaction.response.send_message("\n".join(msg), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Rol verirken hata oluştu: {e}", ephemeral=True)

class DynamicRoleMenuView(discord.ui.View):
    def __init__(self, roles_data: list):
        super().__init__(timeout=None)
        self.add_item(DynamicRoleSelect(roles_data))

class FixedRoleSelect(discord.ui.Select):
    def __init__(self, options: list, placeholder: str, custom_id: str, max_values: int = 1):
        super().__init__(
            options=options,
            placeholder=placeholder,
            min_values=1,
            max_values=max_values,
            custom_id=custom_id
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            guild = interaction.guild
            user = interaction.user
            if not guild or not isinstance(user, discord.Member):
                return await interaction.response.send_message("Bu işlem sunucuda yapılmalıdır.", ephemeral=True)

            added = []
            removed = []
            not_found = []

            for val in self.values:
                role = discord.utils.get(guild.roles, name=val)
                if role:
                    if role in user.roles:
                        await user.remove_roles(role)
                        removed.append(role.name)
                    else:
                        await user.add_roles(role)
                        added.append(role.name)
                else:
                    not_found.append(val)

            msg = []
            if added:
                msg.append(f"✅ Eklenen roller: **{', '.join(added)}**")
            if removed:
                msg.append(f"❌ Kaldırılan roller: **{', '.join(removed)}**")
            if not_found:
                msg.append(f"⚠️ Bulunamayan roller: **{', '.join(not_found)}**")
            if not msg:
                msg.append("Rol durumunuz değişmedi.")

            await interaction.response.send_message("\n".join(msg), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Rol verirken hata oluştu: {e}", ephemeral=True)

# --- BOT EVENTS ---

@bot.event
async def on_ready():
    print(f"[{bot.user}] Vassal of Tiamat aktif! Heavenly Court hizmetinde.")
    status_text = bot_data.get("bot_status", "Heavenly Court 🐉")
    activity = discord.Activity(type=discord.ActivityType.watching, name=status_text)
    await bot.change_presence(status=discord.Status.online, activity=activity)

@bot.event
async def on_member_join(member: discord.Member):
    try:
        if member.bot:
            target_role_name = bot_data.get("auto_bot_role", "~ Minions")
            role = discord.utils.get(member.guild.roles, name=target_role_name) or \
                   discord.utils.get(member.guild.roles, name="Minions")
            if role:
                await member.add_roles(role)
                print(f"🤖 Bot {member.name} sunucuya katıldı, '{role.name}' rolü verildi.")
        else:
            target_role_name = bot_data.get("auto_user_role", "~ Oathbound")
            role = discord.utils.get(member.guild.roles, name=target_role_name) or \
                   discord.utils.get(member.guild.roles, name="Oathbound")
            if role:
                await member.add_roles(role)
                print(f"👤 Üye {member.name} sunucuya katıldı, '{role.name}' rolü verildi.")
    except Exception as e:
        print(f"Otomatik rol verme hatası: {e}")

    channel = get_welcome_channel(member.guild)
    if channel:
        msg_template = bot_data.get("welcome_message", config.WELCOME_MESSAGE)
        gif_link = bot_data.get("welcome_gif", "")
        
        formatted_msg = msg_template.format(user=member.mention, server=member.guild.name)
        full_text = f"{formatted_msg}\n{gif_link}".strip()
        await channel.send(full_text)

@bot.event
async def on_member_remove(member: discord.Member):
    channel = get_welcome_channel(member.guild)
    if channel:
        msg_template = bot_data.get("leave_message", config.LEAVE_MESSAGE)
        gif_link = bot_data.get("leave_gif", "")
        
        formatted_msg = msg_template.format(user=member.mention, server=member.guild.name)
        full_text = f"{formatted_msg}\n{gif_link}".strip()
        await channel.send(full_text)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # --- 1. KELİME TÜRETMECE OYUNU ---
    if is_word_game_channel(message.channel):
        word = message.content.strip().lower()

        if not bot_data.get("word_game_last_word"):
            start_w = random.choice(INITIAL_WORDS)
            bot_data["word_game_last_word"] = start_w
            bot_data["word_game_used_words"] = [start_w]
            save_data(bot_data)

        if len(word.split()) == 1 and word.isalpha():
            last_word = bot_data.get("word_game_last_word", "")
            last_user_id = bot_data.get("word_game_last_user_id")
            used_words = bot_data.get("word_game_used_words", [])

            if last_user_id == message.author.id:
                await message.add_reaction("⚠️")
                await message.channel.send(
                    f"⚠️ {message.author.mention}, üst üste iki kelime türetemezsiniz! Başka bir üyenin yazmasını bekleyin.",
                    delete_after=5
                )
                return

            required_start_char = last_word[-1] if last_word else None
            if required_start_char and not word.startswith(required_start_char):
                await message.add_reaction("❌")
                await message.channel.send(
                    f"❌ {message.author.mention}, kelimeniz **'{required_start_char.upper()}'** harfi ile başlamalı!",
                    delete_after=5
                )
                return

            if word in used_words:
                await message.add_reaction("⚠️")
                await message.channel.send(
                    f"⚠️ {message.author.mention}, **'{word.upper()}'** kelimesi bu turda zaten kullanıldı!",
                    delete_after=5
                )
                return

            is_valid = await is_valid_tdk_word(word)
            if not is_valid:
                await message.add_reaction("❓")
                await message.channel.send(
                    f"❓ {message.author.mention}, **'{word.upper()}'** TDK sözlüğünde bulunamadı!",
                    delete_after=5
                )
                return

            base_points = len(word)
            ends_with_g = word.endswith("ğ")
            total_points = base_points + 10 if ends_with_g else base_points

            scores = bot_data.setdefault("word_game_scores", {})
            user_id_str = str(message.author.id)
            scores[user_id_str] = scores.get(user_id_str, 0) + total_points

            used_words.append(word)

            if ends_with_g:
                await message.add_reaction("🏆")
                new_start_word = random.choice(INITIAL_WORDS)
                bot_data["word_game_last_word"] = new_start_word
                bot_data["word_game_last_user_id"] = None
                bot_data["word_game_used_words"] = [new_start_word]
                save_data(bot_data)

                await message.channel.send(
                    f"🎉 **EFSANEVİ HAMLE!** {message.author.mention} **'Ğ'** ile biten **'{word.upper()}'** kelimesini söyledi!\n"
                    f"⭐ **+{total_points} Puan** kazandı!\n\n"
                    f"🔄 **Tur Sıfırlandı!** Yeni Başlangıç Kelimesi: **{new_start_word.upper()}**\n"
                    f"👉 Sonraki kelime **'{new_start_word[-1].upper()}'** harfi ile başlamalı!"
                )
            else:
                await message.add_reaction("✅")
                bot_data["word_game_last_word"] = word
                bot_data["word_game_last_user_id"] = message.author.id
                bot_data["word_game_used_words"] = used_words
                save_data(bot_data)

                await message.channel.send(
                    f"✅ **{word.upper()}** kabul edildi! (+{total_points} Puan) ➔ Sonraki kelime **'{word[-1].upper()}'** ile başlamalı!",
                    delete_after=7
                )
            return

    # --- 2. SAYI SAYMACA OYUNU ---
    if is_count_game_channel(message.channel):
        content_str = message.content.strip()

        if content_str.isdigit():
            num = int(content_str)
            current_expected = bot_data.get("count_game_current", 1)
            last_user_id = bot_data.get("count_game_last_user_id")

            if last_user_id == message.author.id:
                await message.add_reaction("⚠️")
                await message.channel.send(
                    f"⚠️ {message.author.mention}, üst üste iki sayı sayamazsınız! Başka birinin yazmasını bekleyin. (Sıradaki sayı: **{current_expected}**)",
                    delete_after=5
                )
                return

            if num == current_expected:
                await message.add_reaction("✅")
                bot_data["count_game_current"] = current_expected + 1
                bot_data["count_game_last_user_id"] = message.author.id

                high_score = bot_data.get("count_game_high_score", 0)
                if current_expected > high_score:
                    bot_data["count_game_high_score"] = current_expected

                user_counts = bot_data.setdefault("count_game_user_counts", {})
                user_id_str = str(message.author.id)
                user_counts[user_id_str] = user_counts.get(user_id_str, 0) + 1

                save_data(bot_data)

                if current_expected % 50 == 0:
                    await message.channel.send(f"🎉 **HARİKA İLERLEME!** Sunucu **{current_expected}** sayısına ulaştı! 🚀")
                return

            else:
                await message.add_reaction("💥")
                failed_at = current_expected - 1
                bot_data["count_game_current"] = 1
                bot_data["count_game_last_user_id"] = None
                save_data(bot_data)

                await message.channel.send(
                    f"💥 {message.author.mention} yanlış sayı yazdı! (**{num}** yazıldı, **{current_expected}** bekleniyordu).\n"
                    f"📊 Ulaşılan Rekor Sayı: **{failed_at}**\n"
                    f"🔄 **Sayı Sıfırlandı!** Yeni sayı: **1**"
                )
                return

    # --- NORMAL OTO CEVAP MANTIĞI ---
    content_lower = message.content.strip().lower()
    merged_responses = dict(config.AUTO_RESPONSES)
    merged_responses.update(bot_data.get("custom_responses", {}))

    for trigger, data in merged_responses.items():
        trigger_lower = trigger.lower()
        is_match = False

        if data.get("wildcard", False):
            if trigger_lower in content_lower:
                is_match = True
        else:
            if content_lower == trigger_lower:
                is_match = True

        if is_match:
            responses = data.get("responses", [])
            if responses:
                chosen_response = random.choice(responses)
                await message.channel.send(chosen_response)
            break

    await bot.process_commands(message)

# --- SAYI SAYMACA KOMUTLARI ---

@bot.tree.command(name="sayi_oyunu_baslat", description="Sayı Saymaca oyununu bulunulan kanalda başlatır.")
@app_commands.checks.has_permissions(administrator=True)
async def start_count_game(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel

        bot_data["count_game_channel_id"] = channel.id
        bot_data["count_game_current"] = 1
        bot_data["count_game_last_user_id"] = None
        save_data(bot_data)

        embed = discord.Embed(
            title="🔢 Sayı Saymaca Oyunu Başladı!",
            description=f"Bu kanal ({channel.mention}) Sayı Saymaca kanalı olarak ayarlandı.\n\n"
                        f"📌 **Kurallar:**\n"
                        f"• Sayılar **1**'den başlayarak sırayla yazılmalıdır (`1`, `2`, `3`...).\n"
                        f"• ⚠️ **Aynı kişi üst üste iki sayı yazamaz!**\n"
                        f"• Yanlış sayı yazılırsa sayaç patlar ve **1**'den yeniden başlar!\n\n"
                        f"🚀 **Sıradaki Sayı:** **1**",
            color=discord.Color.blue()
        )
        await channel.send(embed=embed)
        await interaction.followup.send("✅ Sayı saymaca oyunu bu kanalda başlatıldı!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="sayi_oyunu_durdur", description="Sayı Saymaca oyununu durdurur.")
@app_commands.checks.has_permissions(administrator=True)
async def stop_count_game(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        bot_data["count_game_channel_id"] = None
        save_data(bot_data)
        await interaction.followup.send("🛑 Sayı saymaca oyunu durduruldu.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="sayi_rekoru", description="Sayı saymaca oyununun en yüksek rekorunu ve en çok sayanları gösterir.")
async def show_count_game_stats(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        high_score = bot_data.get("count_game_high_score", 0)
        current = bot_data.get("count_game_current", 1)
        user_counts = bot_data.get("count_game_user_counts", {})

        sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_text = []
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i, (user_id, count) in enumerate(sorted_users):
            member = interaction.guild.get_member(int(user_id))
            name = member.mention if member else f"Kullanıcı ({user_id})"
            medal = medals[i] if i < len(medals) else "🏅"
            top_text.append(f"{medal} {name} ➔ **{count} Sayı Saydı**")

        embed = discord.Embed(title="📊 Sayı Saymaca İstatistikleri & Rekorlar", color=discord.Color.teal())
        embed.add_field(name="🏆 Tüm Zamanların Rekoru", value=f"**{high_score}** sayısına ulaşıldı!", inline=False)
        embed.add_field(name="🔢 Mevcut Aktif Sayı", value=f"Sıradaki sayı: **{current}**", inline=False)
        embed.add_field(name="👥 En Çok Katkı Sağlayanlar", value="\n".join(top_text) if top_text else "Henüz kimse saymadı.", inline=False)

        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

# --- KELİME OYUNU KOMUTLARI ---

@bot.tree.command(name="kelime_oyunu_baslat", description="Kelime Türetmece oyununu bulunulan kanalda başlatır.")
@app_commands.checks.has_permissions(administrator=True)
async def start_word_game(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        start_word = random.choice(INITIAL_WORDS)

        bot_data["word_game_channel_id"] = channel.id
        bot_data["word_game_last_word"] = start_word
        bot_data["word_game_last_user_id"] = None
        bot_data["word_game_used_words"] = [start_word]
        save_data(bot_data)

        embed = discord.Embed(
            title="🎮 Kelime Türetmece Oyunu Başladı!",
            description=f"Bu kanal ({channel.mention}) Kelime Türetmece kanalı olarak ayarlandı.\n\n"
                        f"📌 **Kurallar:**\n"
                        f"• TDK sözlüğünde geçen Türkçe kelimeler yazılmalıdır.\n"
                        f"• Her kelime, bir önceki kelimenin **son harfi** ile başlamalıdır.\n"
                        f"• ⚠️ **Aynı kişi üst üste iki kelime yazamaz!**\n"
                        f"• Kelime uzunluğu kadar puan kazanırsınız.\n"
                        f"• **'Ğ'** ile biten kelime yazan **+10 Bonus Puan** kazanır ve turu bitirip yeni kelime başlatır!\n\n"
                        f"🚀 **Başlangıç Kelimesi:** **{start_word.upper()}**\n"
                        f"👉 İlk kelimeniz **'{start_word[-1].upper()}'** harfi ile başlamalıdır!",
            color=discord.Color.green()
        )
        await channel.send(embed=embed)
        await interaction.followup.send("✅ Kelime oyunu bu kanalda başarıyla başlatıldı!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="kelime_oyunu_durdur", description="Kelime Türetmece oyununu durdurur.")
@app_commands.checks.has_permissions(administrator=True)
async def stop_word_game(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        bot_data["word_game_channel_id"] = None
        save_data(bot_data)
        await interaction.followup.send("🛑 Kelime oyunu durduruldu.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="skor_tablosu", description="Kelime türetmece oyunu en yüksek puanlı oyuncuları gösterir.")
async def show_word_game_leaderboard(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        scores = bot_data.get("word_game_scores", {})
        if not scores:
            return await interaction.followup.send("🏆 Henüz kimse kelime oyununda puan kazanmadı.")

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
        leaderboard_text = []
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i, (user_id, score) in enumerate(sorted_scores):
            member = interaction.guild.get_member(int(user_id))
            name = member.mention if member else f"Kullanıcı ({user_id})"
            medal = medals[i] if i < len(medals) else "🏅"
            leaderboard_text.append(f"{medal} {name} ➔ **{score} Puan**")

        embed = discord.Embed(
            title="🏆 Kelime Türetmece Liderlik Tablosu",
            description="\n".join(leaderboard_text),
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

# --- DİĞER SLASH KOMUTLARI ---

@bot.tree.command(name="otorol_ayarla", description="Sunucuya yeni katılan kişilere ve botlara verilecek rolleri ayarlar.")
@app_commands.checks.has_permissions(administrator=True)
async def set_autoroles(interaction: discord.Interaction, insan_rolu: discord.Role = None, bot_rolu: discord.Role = None):
    try:
        await interaction.response.defer(ephemeral=True)
        msg = []
        if insan_rolu:
            bot_data["auto_user_role"] = insan_rolu.name
            msg.append(f"👤 İnsan üyeler için otorol: **{insan_rolu.name}**")
        if bot_rolu:
            bot_data["auto_bot_role"] = bot_rolu.name
            msg.append(f"🤖 Botlar için otorol: **{bot_rolu.name}**")

        if not msg:
            return await interaction.followup.send("Lütfen en az bir rol belirtin.", ephemeral=True)

        save_data(bot_data)
        await interaction.followup.send("✅ Otomatik rol ayarları güncellendi!\n" + "\n".join(msg), ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="otorol_bilgisi", description="Mevcut otomatik verilecek rolleri gösterir.")
@app_commands.checks.has_permissions(administrator=True)
async def show_autorole_info(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🎭 Otomatik Rol Ayarları", color=discord.Color.green())
        embed.add_field(name="👤 Gelen Üyelere Verilecek Rol", value=bot_data.get("auto_user_role", "~ Oathbound"), inline=False)
        embed.add_field(name="🤖 Gelen Botlara Verilecek Rol", value=bot_data.get("auto_bot_role", "~ Minions"), inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="karsilama_kanali_yap", description="Bulunulan kanalı veya seçilen kanalı Hoşgeldin/Görüşürüz kanalı yapar.")
@app_commands.checks.has_permissions(administrator=True)
async def set_current_as_welcome_channel(interaction: discord.Interaction, kanal: discord.TextChannel = None):
    try:
        await interaction.response.defer(ephemeral=True)
        target_channel = kanal or interaction.channel
        bot_data["welcome_channel_id"] = target_channel.id
        save_data(bot_data)
        await interaction.followup.send(f"✅ Hoşgeldin & Görüşürüz kanalı {target_channel.mention} olarak ayarlandı!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="karsilama_mesaji_ayarla", description="Giriş yapıldığında atılacak metni değiştirir ({user} etiketi destekler).")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_message(interaction: discord.Interaction, mesaj: str):
    try:
        await interaction.response.defer(ephemeral=True)
        bot_data["welcome_message"] = mesaj
        save_data(bot_data)
        await interaction.followup.send(f"✅ Karşılama mesajı güncellendi!\n**Yeni Mesaj:** {mesaj}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="karsilama_gif_ayarla", description="Giriş yapıldığında gönderilecek GIF linkini değiştirir.")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_gif(interaction: discord.Interaction, gif_url: str):
    try:
        await interaction.response.defer(ephemeral=True)
        bot_data["welcome_gif"] = gif_url
        save_data(bot_data)
        await interaction.followup.send(f"✅ Karşılama GIF linki güncellendi!\n**GIF:** {gif_url}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="ugurlama_mesaji_ayarla", description="Biri ayrıldığında atılacak metni değiştirir ({user} etiketi destekler).")
@app_commands.checks.has_permissions(administrator=True)
async def set_leave_message(interaction: discord.Interaction, mesaj: str):
    try:
        await interaction.response.defer(ephemeral=True)
        bot_data["leave_message"] = mesaj
        save_data(bot_data)
        await interaction.followup.send(f"✅ Uğurlama mesajı güncellendi!\n**Yeni Mesaj:** {mesaj}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="ugurlama_gif_ayarla", description="Biri ayrıldığında gönderilecek GIF linkini değiştirir.")
@app_commands.checks.has_permissions(administrator=True)
async def set_leave_gif(interaction: discord.Interaction, gif_url: str):
    try:
        await interaction.response.defer(ephemeral=True)
        bot_data["leave_gif"] = gif_url
        save_data(bot_data)
        await interaction.followup.send(f"✅ Uğurlama GIF linki güncellendi!\n**GIF:** {gif_url}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="karsilama_bilgisi", description="Mevcut karşılama ve uğurlama ayarlarını gösterir.")
@app_commands.checks.has_permissions(administrator=True)
async def show_welcome_info(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        channel = get_welcome_channel(interaction.guild)
        channel_str = channel.mention if channel else "Varsayılan"
        
        embed = discord.Embed(title="⚙️ Karşılama & Uğurlama Ayarları", color=discord.Color.blue())
        embed.add_field(name="📍 Aktif Kanal", value=channel_str, inline=False)
        embed.add_field(name="👋 Karşılama Mesajı", value=bot_data.get("welcome_message"), inline=False)
        embed.add_field(name="🖼️ Karşılama GIF", value=bot_data.get("welcome_gif") or "Yok", inline=False)
        embed.add_field(name="🚪 Uğurlama Mesajı", value=bot_data.get("leave_message"), inline=False)
        embed.add_field(name="🖼️ Uğurlama GIF", value=bot_data.get("leave_gif") or "Yok", inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="otocevap_ekle", description="Bota yeni bir otomatik cevap/GIF yanıtı ekler.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    tetikleyici="Tetikleyici kelime veya cümle (Örn: naber)",
    yanit="Botun vereceği cevap veya GIF linki",
    wildcard="True ise cümlenin herhangi bir yerinde geçmesi yeterlidir"
)
async def add_custom_response(interaction: discord.Interaction, tetikleyici: str, yanit: str, wildcard: bool = False):
    try:
        await interaction.response.defer(ephemeral=True)
        key = tetikleyici.strip().lower()
        customs = bot_data.setdefault("custom_responses", {})
        
        if key in customs:
            if yanit not in customs[key]["responses"]:
                customs[key]["responses"].append(yanit)
            customs[key]["wildcard"] = wildcard
        else:
            customs[key] = {
                "responses": [yanit],
                "wildcard": wildcard
            }
        
        save_data(bot_data)
        await interaction.followup.send(
            f"✅ **'{key}'** için yeni yanıt eklendi!\n💬 **Eklendi:** {yanit}\n🔍 **Wildcard:** {wildcard}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="otocevap_sil", description="Eklenmiş bir otomatik cevabı siler.")
@app_commands.checks.has_permissions(administrator=True)
async def remove_custom_response(interaction: discord.Interaction, tetikleyici: str):
    try:
        await interaction.response.defer(ephemeral=True)
        key = tetikleyici.strip().lower()
        customs = bot_data.get("custom_responses", {})
        
        if key in customs:
            del customs[key]
            save_data(bot_data)
            await interaction.followup.send(f"✅ **'{key}'** oto cevabı başarıyla silindi.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ **'{key}'** adında eklenmiş özel bir oto cevap bulunamadı.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="otocevap_listele", description="Tüm özel ve varsayılan oto cevapları listeler.")
@app_commands.checks.has_permissions(administrator=True)
async def list_custom_responses(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        merged = dict(config.AUTO_RESPONSES)
        merged.update(bot_data.get("custom_responses", {}))

        text_list = []
        for k, v in merged.items():
            resp_count = len(v.get("responses", []))
            wildcard_str = " 🔍(Wildcard)" if v.get("wildcard") else ""
            text_list.append(f"• **{k}**{wildcard_str} ➔ {resp_count} adet yanıt var")

        embed = discord.Embed(
            title="🤖 Mevcut Tüm Oto Cevaplar",
            description="\n".join(text_list) if text_list else "Oto cevap bulunamadı.",
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="ozel_rol_menusu", description="Kendi belirleyeceğiniz rollerle kanala tıklamalı rol menüsü atar.")
@app_commands.checks.has_permissions(administrator=True)
async def create_custom_role_menu(interaction: discord.Interaction, baslik: str, aciklama: str, roller: str):
    try:
        await interaction.response.defer(ephemeral=True)
        
        role_names_or_ids = [r.strip() for r in roller.split(",") if r.strip()]
        if not role_names_or_ids:
            return await interaction.followup.send("Lütfen en az bir rol ismi veya ID yazın.", ephemeral=True)

        roles_data = []
        guild = interaction.guild

        for item in role_names_or_ids:
            r = get_role_by_identifier(guild, item)
            if r:
                roles_data.append({"label": r.name, "value": r.id})
            else:
                roles_data.append({"label": item, "value": item})

        view = DynamicRoleMenuView(roles_data)
        embed = discord.Embed(
            title=baslik,
            description=f"{aciklama}\n\n**Seçilebilir Roller:**\n" + "\n".join([f"• {r['label']}" for r in roles_data]),
            color=discord.Color.purple()
        )

        await interaction.channel.send(embed=embed, view=view)
        await interaction.followup.send("✅ Özel rol menüsü kanala gönderildi!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="rol_olustur", description="Sunucuda yeni bir rol oluşturur.")
@app_commands.checks.has_permissions(administrator=True)
async def create_single_role(interaction: discord.Interaction, rol_adi: str):
    try:
        await interaction.response.defer(ephemeral=True)
        role = await interaction.guild.create_role(name=rol_adi, reason="Vassal of Tiamat komutu ile oluşturuldu.")
        await interaction.followup.send(f"✅ **{role.name}** rolü başarıyla oluşturuldu!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

# ----------------- KULLANICI OTO TAMAMLAMA (AUTOCOMPLETE / CHOICES) -----------------

@bot.tree.command(name="rol_menusu", description="Sunucunuzdaki mevcut rol isimleriyle birebir uyumlu menüleri kanala gönderir.")
@app_commands.describe(tur="Gönderilecek rol menüsü kategorisini seçin")
@app_commands.choices(tur=[
    app_commands.Choice(name="🎨 Renk Rolleri", value="renk"),
    app_commands.Choice(name="🎵 Müzik Türü Rolleri", value="muzik"),
    app_commands.Choice(name="📖 İlgi Alanı Rolleri", value="ilgi")
])
@app_commands.checks.has_permissions(administrator=True)
async def send_role_menus(interaction: discord.Interaction, tur: app_commands.Choice[str]):
    try:
        await interaction.response.defer(ephemeral=True)
        selected_type = tur.value.lower()
        
        if selected_type in ["ilgi", "ilgi alanları", "kitap"]:
            options = [
                discord.SelectOption(label="~kitap", emoji="📖", description="Kitap rolü"),
                discord.SelectOption(label="~müzik", emoji="🎵", description="Müzik rolü"),
                discord.SelectOption(label="~resim", emoji="🎨", description="Resim rolü"),
                discord.SelectOption(label="~oyun", emoji="🎮", description="Oyun rolü"),
            ]
            view = discord.ui.View(timeout=None)
            view.add_item(FixedRoleSelect(options=options, placeholder="İlgi alanlarınızı seçin...", custom_id="interest_exact", max_values=4))
            
            embed = discord.Embed(
                title="📖 İlgi Alanları Rol Seçimi",
                description="Aşağıdaki menüden ilgilendiğiniz kategorileri seçerek rol alabilirsiniz:\n\n"
                            "📖 **~kitap** | 🎵 **~müzik** | 🎨 **~resim** | 🎮 **~oyun**",
                color=discord.Color.blue()
            )
            await interaction.channel.send(embed=embed, view=view)
            await interaction.followup.send("✅ İlgi alanı rol menüsü gönderildi!", ephemeral=True)

        elif selected_type in ["renk", "renkler"]:
            options = [
                discord.SelectOption(label="~kirmizi", emoji="🌹"),
                discord.SelectOption(label="~turuncu", emoji="🍊"),
                discord.SelectOption(label="~sari", emoji="🍋"),
                discord.SelectOption(label="~yesil", emoji="🌲"),
                discord.SelectOption(label="~mavi", emoji="🧿"),
                discord.SelectOption(label="~mor", emoji="🌌"),
                discord.SelectOption(label="~Pembik", emoji="🌷"),
            ]
            view = discord.ui.View(timeout=None)
            view.add_item(FixedRoleSelect(options=options, placeholder="Renk rolünüzü seçin...", custom_id="color_exact", max_values=1))

            embed = discord.Embed(
                title="🎨 Renk Rol Seçimi",
                description="Aşağıdaki menüden sevdiğiniz renk rolünü seçebilirsiniz:\n\n"
                            "🌹 **~kirmizi** | 🍊 **~turuncu** | 🍋 **~sari** | 🌲 **~yesil** | 🌌 **~mor** | 🌷 **~Pembik**",
                color=discord.Color.purple()
            )
            await interaction.channel.send(embed=embed, view=view)
            await interaction.followup.send("✅ Renk rol menüsü gönderildi!", ephemeral=True)

        elif selected_type in ["muzik", "müzik"]:
            options = [
                discord.SelectOption(label="~Bards of the Shire", emoji="🌾", description="Folk / Celtic"),
                discord.SelectOption(label="~Maestro of Dreams", emoji="🎻", description="Symphonic Metal"),
                discord.SelectOption(label="~Ravens of Caradhras", emoji="🐦", description="Gothic Metal"),
                discord.SelectOption(label="~Gloom Weaver", emoji="🕷️", description="Doom Metal"),
                discord.SelectOption(label="~Dragonborn", emoji="🐉", description="Power Metal"),
                discord.SelectOption(label="~Necroharcmonic", emoji="💀", description="Black Metal"),
                discord.SelectOption(label="~Mages of Earthsea", emoji="🔮", description="Progressive Rock/Metal"),
                discord.SelectOption(label="~Demon of Crossroad", emoji="😈", description="Blues"),
                discord.SelectOption(label="~Whisperes of the Void", emoji="🌌", description="Void / Deep Ambient"),
                discord.SelectOption(label="~Nameless Ones", emoji="🎭", description="Nu-metal"),
                discord.SelectOption(label="~ Sons of the Anarchy", emoji="💥", description="Punk"),
                discord.SelectOption(label="~ KillJoys", emoji="🖤", description="Emo"),
                discord.SelectOption(label="~ Dirt in the Wind", emoji="🌪️", description="Grunge"),
                discord.SelectOption(label="~ Echos of Mordor", emoji="⛓️", description="Atmospheric Metal"),
            ]
            view = discord.ui.View(timeout=None)
            view.add_item(FixedRoleSelect(options=options, placeholder="Müzik zevkinizi seçin...", custom_id="music_exact", max_values=14))

            embed = discord.Embed(
                title="🎵 Müzik Türü Rol Seçimi",
                description="Sevdiğiniz müzik tarzlarına göre rol almak için aşağıdaki menüyü kullanın:\n\n"
                            "🌾 **~Bards of the Shire** ➔ Folk / Celtic\n"
                            "🎻 **~Maestro of Dreams** ➔ Symphonic Metal\n"
                            "🐦 **~Ravens of Caradhras** ➔ Gothic Metal\n"
                            "🐉 **~Dragonborn** ➔ Power Metal\n"
                            "🕷️ **~Gloom Weaver** ➔ Doom Metal\n"
                            "💀 **~Necroharcmonic** ➔ Black Metal\n"
                            "🔮 **~Mages of Earthsea** ➔ Progressive Rock/Metal\n"
                            "⛓️ **~ Echos of Mordor** ➔ Atmospheric Metal\n"
                            "🖤 **~ KillJoys** ➔ Emo\n"
                            "💥 **~ Sons of the Anarchy** ➔ Punk\n"
                            "🌪️ **~ Dirt in the Wind** ➔ Grunge\n"
                            "🎭 **~Nameless Ones** ➔ Nu-metal\n"
                            "😈 **~Demon of Crossroad** ➔ Blues\n"
                            "🌌 **~Whisperes of the Void** ➔ Void / Deep Ambient",
                color=discord.Color.dark_red()
            )
            await interaction.channel.send(embed=embed, view=view)
            await interaction.followup.send("✅ Müzik rol menüsü gönderildi!", ephemeral=True)
        else:
            await interaction.followup.send("Geçersiz tür. Kullanılabilir türler: `ilgi`, `renk`, `muzik`", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

@bot.tree.command(name="durum_ayarla", description="Botun oynuyor/izliyor durum metnini değiştirir.")
@app_commands.checks.has_permissions(administrator=True)
async def set_bot_status(interaction: discord.Interaction, durum: str):
    try:
        await interaction.response.defer(ephemeral=True)
        bot_data["bot_status"] = durum
        save_data(bot_data)
        activity = discord.Activity(type=discord.ActivityType.watching, name=durum)
        await bot.change_presence(status=discord.Status.online, activity=activity)
        await interaction.followup.send(f"✅ Bot durumu **'{durum}'** güncellendi!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Hata: {e}", ephemeral=True)

if __name__ == "__main__":
    if not TOKEN:
        print("HATA: .env dosyasında DISCORD_TOKEN bulunamadı!")
    else:
        keep_alive()
        bot.run(TOKEN)
