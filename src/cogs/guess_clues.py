import random
from urllib.parse import quote

import aiohttp
import config
import discord
from discord.ext import commands


RAE_API_URL = "https://rae-api.com/api"
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
    "examples": "Incluye ejemplos de uso",
    "regional": "Tiene algún uso regional",
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

    clues = discord.SlashCommandGroup("clues", "Adivina las pistas de una palabra")

    @clues.command(name="start", description="Inicia una partida en este canal")
    async def start(self, ctx: discord.ApplicationContext):
        if not config.rae_api_key:
            await ctx.respond("RAE_API_KEY no está configurada.", ephemeral=True)
            return
        if ctx.channel.id in self.games:
            await ctx.respond("Ya hay una partida activa en este canal.", ephemeral=True)
            return

        await ctx.defer()
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                word, entry = await random_entry(session)
        except (aiohttp.ClientError, TimeoutError, RaeApiError) as error:
            await ctx.respond(f"No pude iniciar la partida con RAE API: {error}", ephemeral=True)
            return

        target_criteria = matching_criteria(word, entry)
        criteria = choose_round_criteria(target_criteria)
        self.games[ctx.channel.id] = {
            "criteria": criteria,
            "target_criteria": target_criteria,
            "target_word": word,
            "resolved": set(),
            "attempts": 0,
            "owner_id": ctx.author.id,
        }
        game = self.games[ctx.channel.id]
        await ctx.respond(
            "## Guess the Clues\n"
            "Descubre cuáles criterios cumple la palabra objetivo. Cada palabra "
            "válida prueba todos los criterios que ella misma cumple.\n\n"
            f"{format_board(game)}\n\n"
            "Usa `/clues guess palabra:` para jugar."
        )

    @clues.command(name="guess", description="Prueba una palabra española")
    async def guess(self, ctx: discord.ApplicationContext, palabra: str):
        game = self.games.get(ctx.channel.id)
        if game is None:
            await ctx.respond("No hay partida activa. Usa `/clues start`.", ephemeral=True)
            return

        word = normalize_word(palabra)
        if word is None:
            await ctx.respond("Escribe una sola palabra formada únicamente por letras.", ephemeral=True)
            return

        await ctx.defer()
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                entry = await fetch_entry(session, word)
        except (aiohttp.ClientError, TimeoutError, RaeApiError) as error:
            await ctx.respond(f"No pude consultar RAE API: {error}", ephemeral=True)
            return
        if entry is None:
            await ctx.respond(f"`{word}` no aparece en el diccionario.")
            return

        game["attempts"] += 1
        newly_resolved = (
            matching_criteria(word, entry) & set(game["criteria"])
        ) - game["resolved"]
        game["resolved"].update(newly_resolved)
        result = (
            f"Resuelve **{len(newly_resolved)}** criterio(s)."
            if newly_resolved
            else "No resuelve ningún criterio nuevo."
        )
        lines = [f"**{word.upper()}** — {result}", "", format_board(game)]

        hidden = len(set(game["criteria"]) - game["resolved"])
        if hidden == 0:
            lines.append(
                f"\n🎉 {ctx.author.mention} resolvió el tablero en "
                f"{game['attempts']} intentos. La palabra objetivo era "
                f"**{game['target_word'].upper()}**."
            )
            del self.games[ctx.channel.id]
        else:
            lines.append(f"\nQuedan **{hidden}** criterios por resolver.")
        await ctx.respond("\n".join(lines))

    @clues.command(name="status", description="Muestra las pistas descubiertas")
    async def status(self, ctx: discord.ApplicationContext):
        game = self.games.get(ctx.channel.id)
        if game is None:
            await ctx.respond("No hay partida activa. Usa `/clues start`.", ephemeral=True)
            return
        await ctx.respond(f"{format_board(game)}\n\nIntentos: {game['attempts']}")

    @clues.command(name="stop", description="Cancela la partida de este canal")
    async def stop(self, ctx: discord.ApplicationContext):
        game = self.games.get(ctx.channel.id)
        if game is None:
            await ctx.respond("No hay partida activa.", ephemeral=True)
            return
        if ctx.author.id != game["owner_id"]:
            await ctx.respond("Solo quien inició la partida puede cancelarla.", ephemeral=True)
            return
        del self.games[ctx.channel.id]
        await ctx.respond("Partida cancelada.")


def setup(bot):
    bot.add_cog(GuessClues(bot))


def normalize_word(value: str) -> str | None:
    word = value.strip().casefold()
    return word if word and word.isalpha() else None


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
    if sum(letter in VOWELS for letter in word) >= 3:
        matches.add("three_vowels")
    if word[0] == word[-1]:
        matches.add("same_ends")
    matches.update(categories & {"noun", "verb", "adjective", "adverb"})
    matches.update(genders & {"feminine", "masculine"})
    if "masculine_and_feminine" in genders:
        matches.update({"feminine", "masculine"})
    if len(senses) > 1:
        matches.add("multiple_meanings")
    if any(sense.get("synonyms") for sense in senses):
        matches.add("synonyms")
    if any(sense.get("antonyms") for sense in senses):
        matches.add("antonyms")
    if any(sense.get("examples") for sense in senses):
        matches.add("examples")
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
