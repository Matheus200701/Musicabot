from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class PlayerView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.primary, custom_id="music:toggle")
    async def toggle(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        p = self.bot.players; player = p.get(interaction.guild_id)
        if player.voice and player.voice.is_playing(): p.pause(interaction.guild_id); text = "⏸️ Pausado."
        elif player.voice and player.voice.is_paused(): p.resume(interaction.guild_id); text = "▶️ Retomado."
        else: text = "❌ Nada está tocando."
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="music:skip")
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        p = self.bot.players; p.skip(interaction.guild); await interaction.response.send_message("⏭️ Pulando.", ephemeral=True)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="music:shuffle")
    async def shuffle(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.bot.players.shuffle(interaction.guild_id); await interaction.response.send_message("🔀 Fila embaralhada.", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="music:stop")
    async def stop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.bot.players.stop(interaction.guild_id); await interaction.response.send_message("⏹️ Player parado.", ephemeral=True)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot): self.bot = bot

    def _voice(self, interaction: discord.Interaction) -> discord.VoiceChannel | None:
        member = interaction.user
        if isinstance(member, discord.Member) and member.voice and isinstance(member.voice.channel, discord.VoiceChannel): return member.voice.channel
        return None

    @app_commands.command(name="play", description="Pesquisa ou reproduz uma URL")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        channel = self._voice(interaction)
        if not channel: return await interaction.followup.send("❌ Entre em um canal de voz primeiro.")
        try:
            track = await self.bot.players.enqueue(interaction.guild, channel, query, interaction.user.id, search=not query.startswith(("http://", "https://")))
            await interaction.followup.send(f"🎵 **{track.title}** adicionada à fila.", view=PlayerView(self.bot))
        except Exception as exc:
            await interaction.followup.send(f"❌ Não foi possível reproduzir: `{type(exc).__name__}`")

    @app_commands.command(name="search", description="Pesquisa até 10 músicas")
    async def search(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            results = await self.bot.players.resolver.search(query, interaction.user.id, 10)
            if not results: return await interaction.followup.send("❌ Nenhum resultado.")
            await interaction.followup.send(embed=discord.Embed(title="🔎 Resultados", description="Escolha no menu."), view=SearchView(self.bot, results), ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(f"❌ Pesquisa falhou: `{type(exc).__name__}`")

    @app_commands.command(name="pause", description="Pausa")
    async def pause(self, interaction): self.bot.players.pause(interaction.guild_id); await interaction.response.send_message("⏸️ Pausado.")

    @app_commands.command(name="resume", description="Retoma")
    async def resume(self, interaction): self.bot.players.resume(interaction.guild_id); await interaction.response.send_message("▶️ Retomado.")

    @app_commands.command(name="skip", description="Pula")
    async def skip(self, interaction): self.bot.players.skip(interaction.guild); await interaction.response.send_message("⏭️ Pulando.")

    @app_commands.command(name="stop", description="Para e desconecta")
    async def stop(self, interaction): await self.bot.players.stop(interaction.guild_id); await interaction.response.send_message("⏹️ Parado.")

    @app_commands.command(name="queue", description="Mostra a fila")
    async def queue(self, interaction):
        p=self.bot.players.get(interaction.guild_id); text="\n".join(f"{i}. {t.title}" for i,t in enumerate(p.queue,1)) or "(vazia)"; await interaction.response.send_message(f"🎵 **Fila**\n{text}")

    @app_commands.command(name="nowplaying", description="Mostra a música atual")
    async def nowplaying(self, interaction):
        p=self.bot.players.get(interaction.guild_id)
        if not p.current: return await interaction.response.send_message("❌ Nada tocando.")
        e=discord.Embed(title="🎵 Tocando agora",description=p.current.title)
        if p.current.thumbnail: e.set_thumbnail(url=p.current.thumbnail)
        await interaction.response.send_message(embed=e,view=PlayerView(self.bot))

    @app_commands.command(name="volume", description="Volume de 0 a 100")
    async def volume(self, interaction, value: app_commands.Range[int,0,100]):
        p=self.bot.players.get(interaction.guild_id); p.volume=value/100
        if p.voice and isinstance(p.voice.source,discord.PCMVolumeTransformer): p.voice.source.volume=p.volume
        await interaction.response.send_message(f"🔊 Volume: **{value}%**")

    @app_commands.command(name="shuffle", description="Embaralha")
    async def shuffle(self, interaction): self.bot.players.shuffle(interaction.guild_id); await interaction.response.send_message("🔀 Fila embaralhada.")

    @app_commands.command(name="loop", description="Define o loop")
    @app_commands.choices(mode=[app_commands.Choice(name="off",value="off"),app_commands.Choice(name="track",value="track"),app_commands.Choice(name="queue",value="queue")])
    async def loop(self, interaction, mode: app_commands.Choice[str]): self.bot.players.get(interaction.guild_id).loop=mode.value; await interaction.response.send_message(f"🔁 Loop: **{mode.value}**")


class SearchView(discord.ui.View):
    def __init__(self, bot, tracks):
        super().__init__(timeout=120); self.bot=bot; self.tracks=tracks
        select=discord.ui.Select(placeholder="Escolha uma música",options=[discord.SelectOption(label=t.title[:100],value=str(i)) for i,t in enumerate(tracks)])
        select.callback=self.callback; self.add_item(select)

    async def callback(self, interaction):
        track=self.tracks[int(interaction.data["values"][0])]; channel=interaction.user.voice.channel if interaction.user.voice else None
        if not isinstance(channel,discord.VoiceChannel): return await interaction.response.send_message("❌ Entre em voz.",ephemeral=True)
        p=await self.bot.players.connect(interaction.guild_id,channel); p.queue.append(track)
        if not p.voice.is_playing() and not p.voice.is_paused(): await self.bot.players._start_next(interaction.guild)
        await interaction.response.send_message(f"🎵 **{track.title}** adicionada.",ephemeral=True)


async def setup(bot): await bot.add_cog(Music(bot))
