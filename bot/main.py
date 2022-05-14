import requests
from time import sleep
import json

import asyncio
import discord
import youtube_dl
import os

from discord.ext import commands

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id="58ce68abb8894a9ebf78568148651075",
                                                           client_secret="640be1aff9114bb7b5069ade0071af6b"))

TOKEN = os.getenv("DISCORD_TOKEN")

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cola = []
        self.cola_titles = []
    
    @commands.command()
    async def wow_lvls(self, ctx):
        ctx.send("Recuperando información...")
        player_list = ["Romeria", "Felipeperoni", "Jitomitanaka", "Watonne", "Pedroprado", "Dinoosuno", "Wiwiriski"]
        msg = ""
        for player_name in player_list:
            r = requests.get(f"http://armory.warmane.com/api/character/{player_name}/Lordaeron/profile", headers={'User-Agent': 'Custom'})
            player_data = json.loads(r.text)
            name = player_data["name"]
            lvl = player_data["level"]
            data = {"name":name, "lvl":lvl}
            msg += f'{data["name"]} está lvl {data["lvl"]} \n'
            sleep(3)
        await ctx.send(msg)
    
    async def play_next(self, ctx):
        #if ctx.voice_client.is_playing is False:
        loop = asyncio.get_event_loop()
        if len(self.cola) >= 1:
            #player = self.cola.pop(0)
            self.cola_titles.pop(0)
            url = self.cola.pop(0)
            ctx.voice_client.stop()
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            await ctx.send(f'Now playing: {player.title}')
            await ctx.voice_client.play(player, after=lambda e: loop.create_task(self.play_next(ctx)))
            asyncio.run_coroutine_threadsafe(ctx.send("No more songs in queue."))

    @commands.command()
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        """Joins a voice channel"""

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()

    @commands.command()
    async def p(self, ctx, *, url):
        """Streams from a url (same as yt, but doesn't predownload)"""
        loop = asyncio.get_event_loop()

        async with ctx.typing():
            if "https://open.spotify.com/playlist/" in url:
                spotify_query = sp.playlist(url)
                tracks = spotify_query["tracks"]
                track_list = [f'{song["track"]["artists"][0]["name"]} - {song["track"]["name"]}' for song in tracks["items"]]
                url = track_list.pop(0)
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                if ctx.voice_client.is_playing() or len(self.cola) > 0:
                    self.cola.append(url)
                    self.cola_titles.append(player.title)
                    await ctx.send(f'{player.title} added to queue')
                else:
                    ctx.voice_client.play(player, after=lambda e: loop.create_task(self.play_next(ctx)))
                    await ctx.send(f'Now playing: {player.title}')

                if len(track_list) > 0:
                    for track in track_list:
                        url = track
                        self.cola.append(url)
                        self.cola_titles.append(url)
                    await ctx.send(f'Playlist added to queue')

            else:
                if "https://open.spotify.com/track/" in url:
                    #Get artist + song title for single track
                    spotify_query = sp.track(url)
                    url = f'{spotify_query["artists"][0]["name"]} {spotify_query["name"]}'
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
                if ctx.voice_client.is_playing() or len(self.cola) > 0:
                    self.cola.append(url)
                    self.cola_titles.append(player.title)
                    await ctx.send(f'{player.title} added to queue')
                else:
                    ctx.voice_client.play(player, after=lambda e: loop.create_task(self.play_next(ctx)))
                    await ctx.send(f'Now playing: {player.title}')

    @commands.command()
    async def skip(self, ctx):
        ctx.voice_client.stop()
        
        # if len(self.cola) > 0:
        #     self.cola_titles.pop(0)
        #     url = self.cola.pop(0)
        #     player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)            
        #     ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
        #     await ctx.send(f'Now playing: {player.title}')

    @commands.command()
    async def playlist(self, ctx):
        if len(self.cola_titles) > 0:
            cola = f""
            for song_index in range(len(self.cola_titles)):
                # if song_index > 5:
                #     break
                song = self.cola_titles[song_index]
                cola += f"{song_index + 1}. {song}\n"
            await ctx.send(f'{cola}')

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""

        await ctx.voice_client.disconnect()

    @commands.command()
    async def stfu(self, ctx):
        ctx.voice_client.stop()
        self.cola = []
        self.cola_titles = []

    @p.before_invoke
    # @yt.before_invoke
    # @stream.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        # elif ctx.voice_client.is_playing():
            # ctx.voice_client.stop()

bot = commands.Bot(command_prefix=commands.when_mentioned_or("-"),
                   description='Relatively simple music bot example')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

bot.add_cog(Music(bot))
bot.run(TOKEN)