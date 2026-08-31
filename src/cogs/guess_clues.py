import asyncio
import random
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

import aiohttp
import config
import discord
from discord.ext import commands, tasks


RAE_API_URL = "https://rae-api.com/api"
DAILY_TIME_ZONE = ZoneInfo("America/Los_Angeles")
VOWELS = set("aeiouáéíóúü")
CRITERIA = {
    "starts_vowel": "Empieza con vocal",
    "starts_consonant": "Empieza con consonante",
    "ends_vowel": "Termina con vocal",
    "ends_consonant": "Termina con consonante",
    "short": "Tiene entre 4 y 6 letras",
    "medium": "Tiene 7 letras",
    "long": "Tiene entre 8 y 10 letras",
    "accent": "Lleva tilde",
    "enye": "Contiene la letra ñ",
    "contains_h": "Contiene la letra h",
    "double_letter": "Tiene dos letras iguales consecutivas",
    "repeated_letter": "Repite alguna letra",
    "three_vowels": "Tiene al menos tres vocales",
    "same_ends": "Empieza y termina con la misma letra",
    "noun": "Puede ser sustantivo",
    "verb": "Puede ser verbo",
    "adjective": "Puede ser adjetivo",
    "adverb": "Puede ser adverbio",
    "feminine": "Puede ser femenina",
    "masculine": "Puede ser masculina",
    "multiple_meanings": "Tiene varias acepciones",
    "synonyms": "Tiene sinónimos",
    "antonyms": "Tiene antónimos",
    "three_letter_palindrome": "Contiene una secuencia palíndroma de tres letras",
    "regional": "Tiene alguna acepción regional",
}
CRITERION_GROUPS = {
    "starts_vowel": "start",
    "starts_consonant": "start",
    "ends_vowel": "end",
    "ends_consonant": "end",
    "short": "length",
    "medium": "length",
    "long": "length",
    "double_letter": "repeated",
    "repeated_letter": "repeated",
    "feminine": "gender",
    "masculine": "gender",
}


class RaeApiError(Exception):
    pass


class GuessClues(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}
        self.daily_lock = asyncio.Lock()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.leaderboard_loop.is_running():
            self.leaderboard_loop.start()

    def cog_unload(self):
        self.leaderboard_loop.cancel()

    @tasks.loop(minutes=1)
    async def leaderboard_loop(self):
        await self.publish_pending_leaderboard()

    async def publish_pending_leaderboard(self):
        today, _ = daily_window()
        async with self.daily_lock:
            daily = config.clues_store.get_daily_clues()
            if not daily:
                return
            pending = daily.setdefault("pending_leaderboards", [])
            if pending:
                leaderboard = pending[0]
            elif daily.get("date") != today and not daily.get("leaderboard_published"):
                leaderboard = daily
            else:
                return
            channels = config.clues_store.get_leaderboard_channels()
            if not channels:
                return
            published_guilds = leaderboard.setdefault("published_guilds", [])
            for guild_id, channel_id in channels.items():
                if str(guild_id) in published_guilds:
                    continue
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    continue
                try:
                    await channel.send(format_daily_leaderboard(leaderboard))
                except discord.HTTPException as error:
                    print(f"No pude publicar el leaderboard diario en {guild_id}: {error}")
                    continue
                published_guilds.append(str(guild_id))

            if not set(map(str, channels)).issubset(published_guilds):
                config.clues_store.set_daily_clues(daily)
                return
            if pending:
                pending.pop(0)
            else:
                daily["leaderboard_published"] = True
            config.clues_store.set_daily_clues(daily)

    async def get_daily_challenge(self) -> dict:
        await self.publish_pending_leaderboard()
        today, _ = daily_window()
        async with self.daily_lock:
            daily = config.clues_store.get_daily_clues()
            if daily and daily.get("date") == today:
                return daily

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                word, entry = await random_entry(session)
            target_criteria = matching_criteria(word, entry)
            pending = list(daily.get("pending_leaderboards", [])) if daily else []
            if daily and not daily.get("leaderboard_published"):
                pending.append({
                    "date": daily.get("date"),
                    "target_word": daily.get("target_word"),
                    "results": daily.get("results", {}),
                    "published_guilds": daily.get("published_guilds", []),
                })
            daily = {
                "date": today,
                "target_word": word,
                "target_criteria": list(target_criteria),
                "criteria": choose_round_criteria(target_criteria),
                "players": [],
                "attempts": {},
                "results": {},
                "streaks": daily.get("streaks", {}) if daily else {},
                "pending_leaderboards": pending,
                "leaderboard_published": False,
                "published_guilds": [],
            }
            config.clues_store.set_daily_clues(daily)
            return daily

    async def record_daily_attempt(
        self, game: dict, user_id: int, won: bool
    ) -> tuple[str, int, int]:
        today, _ = daily_window()
        async with self.daily_lock:
            daily = config.clues_store.get_daily_clues()
            if (
                game.get("daily_date") != today
                or not daily
                or daily.get("date") != today
            ):
                return "expired", 0, 0
            players = daily.setdefault("players", [])
            user_id = str(user_id)
            attempts = daily.setdefault("attempts", {})
            if user_id in players:
                return (
                    "played",
                    int(attempts.get(user_id, 0)),
                    daily_streak(daily, user_id),
                )
            attempt = int(attempts.get(user_id, 0)) + 1
            attempts[user_id] = attempt
            streak = daily_streak(daily, user_id)
            if won:
                players.append(user_id)
                daily.setdefault("results", {})[user_id] = attempt
                updated_streak = update_daily_streak(
                    daily.get("streaks", {}).get(user_id), today
                )
                daily.setdefault("streaks", {})[user_id] = updated_streak
                streak = updated_streak["count"]
            config.clues_store.set_daily_clues(daily)
            return "ok", attempt, streak

    clues = discord.SlashCommandGroup("clues", "Adivina las pistas de una palabra")

    @clues.command(name="start", description="Inicia una partida individual, cooperativa o diaria")
    async def start(
        self,
        ctx: discord.ApplicationContext,
        modo: str = discord.Option(
            str,
            description="Quién puede jugar esta partida",
            choices=["individual", "cooperativo", "diario"],
            required=False,
            default="individual",
        ),
    ):
        if not config.rae_api_key:
            await ctx.respond("RAE_API_KEY no está configurada.", ephemeral=True)
            return
        if modo == "diario":
            today, reset_at = daily_window()
            daily = config.clues_store.get_daily_clues()
            if (
                daily
                and daily.get("date") == today
                and str(ctx.author.id) in daily.get("players", [])
            ):
                await ctx.respond(
                    daily_wait_message(reset_at, daily_streak(daily, ctx.author.id)),
                    ephemeral=True,
                )
                return
            if any(
                game.get("mode") == "diario" and game["owner_id"] == ctx.author.id
                for game in self.games.values()
            ):
                await ctx.respond("Ya tienes un desafío diario activo.", ephemeral=True)
                return

        key = (ctx.channel.id, None if modo == "cooperativo" else ctx.author.id)
        if key in self.games:
            await ctx.respond("Ya hay una partida activa de ese modo.", ephemeral=True)
            return
        if any(
            channel_id == ctx.channel.id and None in (owner_id, key[1])
            for channel_id, owner_id in self.games
        ):
            await ctx.respond(
                "No se puede mezclar una partida cooperativa con otra modalidad en el mismo canal.",
                ephemeral=True,
            )
            return

        await ctx.defer(ephemeral=modo == "diario")
        try:
            if modo == "diario":
                daily = await self.get_daily_challenge()
                word = daily["target_word"]
                target_criteria = set(daily["target_criteria"])
                criteria = list(daily["criteria"])
                attempts = int(daily.get("attempts", {}).get(str(ctx.author.id), 0))
            else:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    word, entry = await random_entry(session)
                target_criteria = matching_criteria(word, entry)
                criteria = choose_round_criteria(target_criteria)
                attempts = 0
        except (aiohttp.ClientError, TimeoutError, RaeApiError) as error:
            await ctx.respond(f"No pude iniciar la partida con RAE API: {error}", ephemeral=True)
            return
        self.games[key] = {
            "criteria": criteria,
            "target_criteria": target_criteria,
            "target_word": word,
            "resolved": set(),
            "attempts": attempts,
            "owner_id": ctx.author.id,
            "mode": modo,
            "daily_date": daily["date"] if modo == "diario" else None,
        }
        game = self.games[key]
        rules = (
            "Prueba palabras hasta encontrar una que cumpla los tres criterios."
            if modo == "diario"
            else "Descubre los tres criterios que cumple la palabra base. "
            "Cualquier palabra válida que cumpla los tres gana."
        )
        await ctx.respond(
            "## Guess the Clues\n"
            f"Modo **{modo}**.\n"
            f"{rules}\n\n"
            f"{format_board(game)}\n\n"
            "Usa `/clues guess palabra:` para jugar.",
            ephemeral=modo == "diario",
        )

    @clues.command(name="guess", description="Prueba una palabra española")
    async def guess(self, ctx: discord.ApplicationContext, palabra: str):
        key = find_game_key(self.games, ctx.channel.id, ctx.author.id)
        game = self.games.get(key)
        if game is None:
            await ctx.respond("No hay partida activa. Usa `/clues start`.", ephemeral=True)
            return

        private = game.get("mode") == "diario"
        word = normalize_word(palabra)
        if word is None:
            await ctx.respond("Escribe una sola palabra formada únicamente por letras.", ephemeral=True)
            return

        await ctx.defer(ephemeral=private)
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                entry = await fetch_entry(session, word)
        except (aiohttp.ClientError, TimeoutError, RaeApiError) as error:
            await ctx.respond(f"No pude consultar RAE API: {error}", ephemeral=True)
            return
        if entry is None:
            await ctx.respond(f"`{word}` no aparece en el diccionario.", ephemeral=private)
            return
        guess_criteria = matching_criteria(word, entry)
        won = is_winning_guess(game, guess_criteria)

        if private:
            attempt, attempts, streak = await self.record_daily_attempt(game, ctx.author.id, won)
            if attempt != "ok":
                del self.games[key]
                message = (
                    "El desafío diario anterior ya terminó. Inicia el nuevo con "
                    "`/clues start modo:diario`."
                    if attempt == "expired"
                    else daily_wait_message(streak=streak)
                )
                await ctx.respond(message, ephemeral=True)
                return

        if private:
            game["attempts"] = attempts
        else:
            game["attempts"] += 1
        newly_resolved = (
            guess_criteria & set(game["criteria"])
        ) - game["resolved"]
        game["resolved"].update(newly_resolved)
        result = (
            f"Resuelve **{len(newly_resolved)}** criterio(s)."
            if newly_resolved
            else "No resuelve ningún criterio nuevo."
        )
        remaining = remaining_correct_criteria(game)
        if won:
            game["resolved"].update(game["criteria"])
        lines = [f"**{word.upper()}** — {result}", "", format_board(game)]

        if private:
            if won:
                lines.append("\n🎉 Cumpliste los tres criterios.")
                attempt_unit = "intento" if game["attempts"] == 1 else "intentos"
                lines.append(f"\n🎯 Lo resolviste en **{game['attempts']} {attempt_unit}**.")
                unit = "día" if streak == 1 else "días"
                lines.append(f"\n🔥 Tu racha: **{streak} {unit}**.")
                lines.append(f"\n{daily_wait_message()}")
                del self.games[key]
            else:
                lines.append(
                    "\nNo cumpliste los tres criterios simultáneamente. "
                    "Puedes volver a intentarlo."
                )
                lines.append(f"\nIntentos: **{game['attempts']}**.")
            await ctx.respond("\n".join(lines), ephemeral=True)
            return

        if won:
            lines.append(
                f"\n🎉 {ctx.author.mention} resolvió el tablero en "
                f"{game['attempts']} intentos. Palabra base: "
                f"**{game['target_word'].upper()}**."
            )
            del self.games[key]
        elif remaining:
            lines.append(f"\nQuedan **{len(remaining)}** criterios correctos por descubrir.")
        else:
            lines.append("\nYa conoces los tres criterios. Prueba una palabra que cumpla los tres a la vez.")
        await ctx.respond("\n".join(lines))

    @clues.command(name="status", description="Muestra las pistas descubiertas")
    async def status(self, ctx: discord.ApplicationContext):
        key = find_game_key(self.games, ctx.channel.id, ctx.author.id)
        game = self.games.get(key)
        if game is None:
            await ctx.respond("No hay partida activa. Usa `/clues start`.", ephemeral=True)
            return
        await ctx.respond(
            f"{format_board(game)}\n\nIntentos: {game['attempts']}",
            ephemeral=game.get("mode") == "diario",
        )

    @clues.command(name="stop", description="Cancela la partida de este canal")
    async def stop(self, ctx: discord.ApplicationContext):
        key = find_game_key(self.games, ctx.channel.id, ctx.author.id)
        game = self.games.get(key)
        if game is None:
            await ctx.respond("No hay partida activa.", ephemeral=True)
            return
        if ctx.author.id != game["owner_id"]:
            await ctx.respond("Solo quien inició la partida puede cancelarla.", ephemeral=True)
            return
        private = game.get("mode") == "diario"
        del self.games[key]
        await ctx.respond("Partida cancelada.", ephemeral=private)


def setup(bot):
    bot.add_cog(GuessClues(bot))


def daily_window(now: datetime | None = None) -> tuple[str, int]:
    now = now or datetime.now(timezone.utc)
    pacific = now.astimezone(DAILY_TIME_ZONE)
    reset_at = datetime.combine(
        pacific.date() + timedelta(days=1), time.min, DAILY_TIME_ZONE
    )
    return pacific.date().isoformat(), int(reset_at.timestamp())


def daily_wait_message(reset_at: int | None = None, streak: int | None = None) -> str:
    if reset_at is None:
        _, reset_at = daily_window()
    message = f"Ya has jugado hoy. Siguiente desafío: <t:{reset_at}:R>."
    if streak is None:
        return message
    unit = "día" if streak == 1 else "días"
    return f"{message}\n🔥 Tu racha: **{streak} {unit}**."


def daily_streak(daily: dict, user_id: int | str) -> int:
    return int(daily.get("streaks", {}).get(str(user_id), {}).get("count", 0))


def update_daily_streak(streak: dict | None, today: str) -> dict:
    yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    count = (
        int((streak or {}).get("count", 0)) + 1
        if (streak or {}).get("last_win") == yesterday
        else 1
    )
    return {"count": count, "last_win": today}


def format_daily_leaderboard(daily: dict) -> str:
    day = daily.get("date", "")
    word = str(daily.get("target_word") or "?").upper()
    header = f"## 🏆 Ranking diario — {day}\nPalabra base: **{word}**"
    results = daily.get("results", {})
    if not results:
        return f"{header}\n\nNadie resolvió el desafío."
    groups = {}
    for user_id, attempts in results.items():
        groups.setdefault(int(attempts), []).append(str(user_id))
    lines = [header]
    medals = ("🥇", "🥈", "🥉")
    for place, attempts in enumerate(sorted(groups)[:3]):
        users = ", ".join(f"<@{user_id}>" for user_id in sorted(groups[attempts]))
        unit = "intento" if attempts == 1 else "intentos"
        lines.append(f"{medals[place]} **{place + 1}.º** {users} — **{attempts} {unit}**")
    return "\n\n".join(lines)


def normalize_word(value: str) -> str | None:
    word = value.strip().casefold()
    return word if word and word.isalpha() else None


def find_game_key(games: dict, channel_id: int, user_id: int) -> tuple | None:
    return next((key for key in ((channel_id, user_id), (channel_id, None)) if key in games), None)


def matching_criteria(word: str, entry: dict) -> set[str]:
    senses = [
        sense
        for meaning in entry.get("meanings") or []
        for sense in meaning.get("senses") or []
    ]
    categories = {sense.get("category") for sense in senses}
    genders = {sense.get("gender") for sense in senses}
    matches = set()
    matches.add("starts_vowel" if word[0] in VOWELS else "starts_consonant")
    matches.add("ends_vowel" if word[-1] in VOWELS else "ends_consonant")
    if 4 <= len(word) <= 6:
        matches.add("short")
    elif len(word) == 7:
        matches.add("medium")
    elif 8 <= len(word) <= 10:
        matches.add("long")
    if set(word) & set("áéíóú"):
        matches.add("accent")
    if "ñ" in word:
        matches.add("enye")
    if "h" in word:
        matches.add("contains_h")
    if any(left == right for left, right in zip(word, word[1:])):
        matches.add("double_letter")
    if len(set(word)) < len(word):
        matches.add("repeated_letter")
    if any(word[index] == word[index + 2] for index in range(len(word) - 2)):
        matches.add("three_letter_palindrome")
    if sum(letter in VOWELS for letter in word) >= 3:
        matches.add("three_vowels")
    if word[0] == word[-1]:
        matches.add("same_ends")
    matches.update(categories & {"noun", "verb", "adjective", "adverb"})
    matches.update(genders & {"feminine", "masculine"})
    if "adjective" in categories and word.endswith("a"):
        matches.add("feminine")
    elif "adjective" in categories and word.endswith("o"):
        matches.add("masculine")
    if "masculine_and_feminine" in genders:
        matches.update({"feminine", "masculine"})
    if len(senses) > 1:
        matches.add("multiple_meanings")
    if any(sense.get("synonyms") for sense in senses):
        matches.add("synonyms")
    if any(sense.get("antonyms") for sense in senses):
        matches.add("antonyms")
    if any(sense.get("regions") for sense in senses):
        matches.add("regional")
    return matches


def choose_round_criteria(target_criteria: set[str]) -> list[str]:
    selected = []
    used_groups = set()
    for pool, count in (
        (list(target_criteria), 3),
        (list(set(CRITERIA) - target_criteria), 5),
    ):
        random.shuffle(pool)
        added = 0
        for key in pool:
            group = CRITERION_GROUPS.get(key, key)
            if group in used_groups:
                continue
            selected.append(key)
            used_groups.add(group)
            added += 1
            if added == count:
                break
        if added < count:
            raise ValueError("No hay suficientes criterios compatibles")
    random.shuffle(selected)
    return selected


def format_board(game: dict) -> str:
    lines = []
    for key in game["criteria"]:
        if key not in game["resolved"]:
            marker = "❓"
        elif key in game["target_criteria"]:
            marker = "✅"
        else:
            marker = "❌"
        lines.append(f"{marker} {CRITERIA[key]}")
    return "\n".join(lines)


def remaining_correct_criteria(game: dict) -> set[str]:
    return (set(game["criteria"]) & game["target_criteria"]) - game["resolved"]


def is_winning_guess(game: dict, guess_criteria: set[str]) -> bool:
    return (set(game["criteria"]) & game["target_criteria"]) <= guess_criteria


async def random_entry(session: aiohttp.ClientSession) -> tuple[str, dict]:
    min_length, max_length = random.choice(((4, 6), (7, 7), (8, 10)))
    for _ in range(5):
        payload = await request_json(
            session,
            f"{RAE_API_URL}/random",
            params={"min_length": min_length, "max_length": max_length},
        )
        word = normalize_word(payload.get("data", {}).get("word", ""))
        if word:
            entry = await fetch_entry(session, word)
            if entry and len(matching_criteria(word, entry)) >= 3:
                return word, entry
    raise RaeApiError("no encontré una palabra adecuada")


async def fetch_entry(session: aiohttp.ClientSession, word: str) -> dict | None:
    return await request_json(session, f"{RAE_API_URL}/words/{quote(word, safe='')}", allow_missing=True)


async def request_json(
    session: aiohttp.ClientSession,
    url: str,
    params: dict | None = None,
    allow_missing: bool = False,
) -> dict | None:
    headers = {"X-API-Key": config.rae_api_key}
    async with session.get(url, params=params, headers=headers) as response:
        if allow_missing and response.status == 404:
            return None
        if response.status != 200:
            raise RaeApiError(f"respondió con HTTP {response.status}")
        payload = await response.json()
        if not payload.get("ok"):
            raise RaeApiError(str(payload.get("error") or "respuesta inválida"))
        return payload.get("data") if allow_missing else payload
