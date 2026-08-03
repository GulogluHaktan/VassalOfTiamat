import os
import json
import random
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

import config
from keep_alive import keep_alive

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

DATA_FILE = "bot_data.json"

DEFAULT_DATA = {
    "welcome_channel_id": None,
    "welcome_message": "{user} sunucumuza katıldı,Hoşgeldin!!",
    "welcome_gif": "https://tenor.com/bsXRE.gif",
    "leave_message": "{user} aramızdan ayrıldı...Helvası neyli olsun bu arada-",
    "leave_gif": "https://tenor.com/betLZ.gif",
    "bot_status": "Heavenly Court 🐉",
    "auto_user_role": "~ Oathbound",
    "auto_bot_role": "~ Minions",
    "custom_responses": {}
}

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in DEFAULT_DATA.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as e:
            print(f"Veri yükleme hatası: {e}")
            return dict(DEFAULT_DATA)
    return dict(DEFAULT_DATA)

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Veri kaydetme hatası: {e}")

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

bot = VassalBot()

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
        super().__init__(
            placeholder="Rollerinizi seçin...",
            min_values=0,
            max_values=len(options),
            custom_id=f"dyn_select_{random.randint(10000, 99999)}"
        )

    async def callback(self, interaction: discord.Interaction):
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

class DynamicRoleMenuView(discord.ui.View):
    def __init__(self, roles_data: list):
        super().__init__(timeout=None)
        self.add_item(DynamicRoleSelect(roles_data))

class FixedRoleSelect(discord.ui.Select):
    def __init__(self, options: list, placeholder: str, custom_id: str):
        super().__init__(placeholder=placeholder, min_values=0, max_values=len(options), custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
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

    channel = None
    welcome_id = bot_data.get("welcome_channel_id")
    if welcome_id:
        channel = member.guild.get_channel(welcome_id)
    
    if not channel:
        channel = discord.utils.get(member.guild.text_channels, name="giriş-çıkış") or \
                  discord.utils.get(member.guild.text_channels, name="welcome") or \
                  discord.utils.get(member.guild.text_channels, name="genel") or \
                  member.guild.system_channel

    if channel:
        msg_template = bot_data.get("welcome_message", config.WELCOME_MESSAGE)
        gif_link = bot_data.get("welcome_gif", "")
        
        formatted_msg = msg_template.format(user=member.mention, server=member.guild.name)
        full_text = f"{formatted_msg}\n{gif_link}".strip()
        await channel.send(full_text)

@bot.event
async def on_member_remove(member: discord.Member):
    channel = None
    welcome_id = bot_data.get("welcome_channel_id")
    if welcome_id:
        channel = member.guild.get_channel(welcome_id)
        
    if not channel:
        channel = discord.utils.get(member.guild.text_channels, name="giriş-çıkış") or \
                  discord.utils.get(member.guild.text_channels, name="welcome") or \
                  discord.utils.get(member.guild.text_channels, name="genel") or \
                  member.guild.system_channel

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

# --- SLASH KOMUTLARI ---

@bot.tree.command(name="otorol_ayarla", description="Sunucuya yeni katılan kişilere ve botlara verilecek rolleri ayarlar.")
@app_commands.checks.has_permissions(administrator=True)
async def set_autoroles(interaction: discord.Interaction, insan_rolu: discord.Role = None, bot_rolu: discord.Role = None):
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

@bot.tree.command(name="otorol_bilgisi", description="Mevcut otomatik verilecek rolleri gösterir.")
@app_commands.checks.has_permissions(administrator=True)
async def show_autorole_info(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="🎭 Otomatik Rol Ayarları", color=discord.Color.green())
    embed.add_field(name="👤 Gelen Üyelere Verilecek Rol", value=bot_data.get("auto_user_role", "~ Oathbound"), inline=False)
    embed.add_field(name="🤖 Gelen Botlara Verilecek Rol", value=bot_data.get("auto_bot_role", "~ Minions"), inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="karsilama_kanali_yap", description="Bulunulan kanalı veya seçilen kanalı Hoşgeldin/Görüşürüz kanalı yapar.")
@app_commands.checks.has_permissions(administrator=True)
async def set_current_as_welcome_channel(interaction: discord.Interaction, kanal: discord.TextChannel = None):
    await interaction.response.defer(ephemeral=True)
    target_channel = kanal or interaction.channel
    bot_data["welcome_channel_id"] = target_channel.id
    save_data(bot_data)
    await interaction.followup.send(f"✅ Hoşgeldin & Görüşürüz kanalı {target_channel.mention} olarak ayarlandı!", ephemeral=True)

@bot.tree.command(name="karsilama_mesaji_ayarla", description="Giriş yapıldığında atılacak metni değiştirir ({user} etiketi destekler).")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_message(interaction: discord.Interaction, mesaj: str):
    await interaction.response.defer(ephemeral=True)
    bot_data["welcome_message"] = mesaj
    save_data(bot_data)
    await interaction.followup.send(f"✅ Karşılama mesajı güncellendi!\n**Yeni Mesaj:** {mesaj}", ephemeral=True)

@bot.tree.command(name="karsilama_gif_ayarla", description="Giriş yapıldığında gönderilecek GIF linkini değiştirir.")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_gif(interaction: discord.Interaction, gif_url: str):
    await interaction.response.defer(ephemeral=True)
    bot_data["welcome_gif"] = gif_url
    save_data(bot_data)
    await interaction.followup.send(f"✅ Karşılama GIF linki güncellendi!\n**GIF:** {gif_url}", ephemeral=True)

@bot.tree.command(name="ugurlama_mesaji_ayarla", description="Biri ayrıldığında atılacak metni değiştirir ({user} etiketi destekler).")
@app_commands.checks.has_permissions(administrator=True)
async def set_leave_message(interaction: discord.Interaction, mesaj: str):
    await interaction.response.defer(ephemeral=True)
    bot_data["leave_message"] = mesaj
    save_data(bot_data)
    await interaction.followup.send(f"✅ Uğurlama mesajı güncellendi!\n**Yeni Mesaj:** {mesaj}", ephemeral=True)

@bot.tree.command(name="ugurlama_gif_ayarla", description="Biri ayrıldığında gönderilecek GIF linkini değiştirir.")
@app_commands.checks.has_permissions(administrator=True)
async def set_leave_gif(interaction: discord.Interaction, gif_url: str):
    await interaction.response.defer(ephemeral=True)
    bot_data["leave_gif"] = gif_url
    save_data(bot_data)
    await interaction.followup.send(f"✅ Uğurlama GIF linki güncellendi!\n**GIF:** {gif_url}", ephemeral=True)

@bot.tree.command(name="karsilama_bilgisi", description="Mevcut karşılama ve uğurlama ayarlarını gösterir.")
@app_commands.checks.has_permissions(administrator=True)
async def show_welcome_info(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    w_id = bot_data.get("welcome_channel_id")
    channel_str = f"<#{w_id}>" if w_id else "Varsayılan (giriş-çıkış / welcome / genel)"
    
    embed = discord.Embed(title="⚙️ Karşılama & Uğurlama Ayarları", color=discord.Color.blue())
    embed.add_field(name="📍 Aktif Kanal", value=channel_str, inline=False)
    embed.add_field(name="👋 Karşılama Mesajı", value=bot_data.get("welcome_message"), inline=False)
    embed.add_field(name="🖼️ Karşılama GIF", value=bot_data.get("welcome_gif") or "Yok", inline=False)
    embed.add_field(name="🚪 Uğurlama Mesajı", value=bot_data.get("leave_message"), inline=False)
    embed.add_field(name="🖼️ Uğurlama GIF", value=bot_data.get("leave_gif") or "Yok", inline=False)
    
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="otocevap_ekle", description="Bota yeni bir otomatik cevap/GIF yanıtı ekler.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    tetikleyici="Tetikleyici kelime veya cümle (Örn: naber)",
    yanit="Botun vereceği cevap veya GIF linki",
    wildcard="True ise cümlenin herhangi bir yerinde geçmesi yeterlidir"
)
async def add_custom_response(interaction: discord.Interaction, tetikleyici: str, yanit: str, wildcard: bool = False):
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

@bot.tree.command(name="otocevap_sil", description="Eklenmiş bir otomatik cevabı siler.")
@app_commands.checks.has_permissions(administrator=True)
async def remove_custom_response(interaction: discord.Interaction, tetikleyici: str):
    await interaction.response.defer(ephemeral=True)
    key = tetikleyici.strip().lower()
    customs = bot_data.get("custom_responses", {})
    
    if key in customs:
        del customs[key]
        save_data(bot_data)
        await interaction.followup.send(f"✅ **'{key}'** oto cevabı başarıyla silindi.", ephemeral=True)
    else:
        await interaction.followup.send(f"❌ **'{key}'** adında eklenmiş özel bir oto cevap bulunamadı.", ephemeral=True)

@bot.tree.command(name="otocevap_listele", description="Tüm özel ve varsayılan oto cevapları listeler.")
@app_commands.checks.has_permissions(administrator=True)
async def list_custom_responses(interaction: discord.Interaction):
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

@bot.tree.command(name="ozel_rol_menusu", description="Kendi belirleyeceğiniz rollerle kanala tıklamalı rol menüsü atar.")
@app_commands.checks.has_permissions(administrator=True)
async def create_custom_role_menu(interaction: discord.Interaction, baslik: str, aciklama: str, roller: str):
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

@bot.tree.command(name="rol_olustur", description="Sunucuda yeni bir rol oluşturur.")
@app_commands.checks.has_permissions(administrator=True)
async def create_single_role(interaction: discord.Interaction, rol_adi: str):
    await interaction.response.defer(ephemeral=True)
    role = await interaction.guild.create_role(name=rol_adi, reason="Vassal of Tiamat komutu ile oluşturuldu.")
    await interaction.followup.send(f"✅ **{role.name}** rolü başarıyla oluşturuldu!", ephemeral=True)

@bot.tree.command(name="rol_menusu", description="Sunucunuzdaki mevcut rol isimleriyle birebir uyumlu menüleri kanala gönderir.")
@app_commands.checks.has_permissions(administrator=True)
async def send_role_menus(interaction: discord.Interaction, tur: str):
    await interaction.response.defer(ephemeral=True)
    tur = tur.lower()
    
    if tur in ["ilgi", "ilgi alanları", "kitap"]:
        options = [
            discord.SelectOption(label="~kitap", emoji="📖", description="Kitap rolü"),
            discord.SelectOption(label="~müzik", emoji="🎵", description="Müzik rolü"),
            discord.SelectOption(label="~resim", emoji="🎨", description="Resim rolü"),
            discord.SelectOption(label="~oyun", emoji="🎮", description="Oyun rolü"),
        ]
        view = discord.ui.View(timeout=None)
        view.add_item(FixedRoleSelect(options, "İlgi alanlarınızı seçin...", "interest_exact"))
        
        embed = discord.Embed(
            title="📖 İlgi Alanları Rol Seçimi",
            description="Aşağıdaki menüden ilgilendiğiniz kategorileri seçerek rol alabilirsiniz:\n\n"
                        "📖 **~kitap** | 🎵 **~müzik** | 🎨 **~resim** | 🎮 **~oyun**",
            color=discord.Color.blue()
        )
        await interaction.channel.send(embed=embed, view=view)
        await interaction.followup.send("✅ İlgi alanı rol menüsü gönderildi!", ephemeral=True)

    elif tur in ["renk", "renkler"]:
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
        view.add_item(FixedRoleSelect(options, "Renk rolünüzü seçin...", "color_exact"))

        embed = discord.Embed(
            title="🎨 Renk Rol Seçimi",
            description="Aşağıdaki menüden sevdiğiniz renk rolünü seçebilirsiniz:\n\n"
                        "🌹 **~kirmizi** | 🍊 **~turuncu** | 🍋 **~sari** | 🌲 **~yesil** | 🧿 **~mavi** | 🌌 **~mor** | 🌷 **~Pembik**",
            color=discord.Color.purple()
        )
        await interaction.channel.send(embed=embed, view=view)
        await interaction.followup.send("✅ Renk rol menüsü gönderildi!", ephemeral=True)

    elif tur in ["muzik", "müzik"]:
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
        view.add_item(FixedRoleSelect(options, "Müzik zevkinizi seçin...", "music_exact"))

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

@bot.tree.command(name="durum_ayarla", description="Botun oynuyor/izliyor durum metnini değiştirir.")
@app_commands.checks.has_permissions(administrator=True)
async def set_bot_status(interaction: discord.Interaction, durum: str):
    await interaction.response.defer(ephemeral=True)
    bot_data["bot_status"] = durum
    save_data(bot_data)
    activity = discord.Activity(type=discord.ActivityType.watching, name=durum)
    await bot.change_presence(status=discord.Status.online, activity=activity)
    await interaction.followup.send(f"✅ Bot durumu **'{durum}'** olarak güncellendi!", ephemeral=True)

if __name__ == "__main__":
    if not TOKEN:
        print("HATA: .env dosyasında DISCORD_TOKEN bulunamadı!")
    else:
        keep_alive()
        bot.run(TOKEN)
