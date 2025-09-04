import os
import asyncpg
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo  # Python 3.9+
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")
PG_DATABASE = os.getenv("PG_DATABASE", "postgres")

# Discord intents
INTENTS = discord.Intents.default()
INTENTS.message_content = True  # for prefix commands

bot = commands.Bot(command_prefix="!", intents=INTENTS)
tree = bot.tree  # Slash command tree

pool: asyncpg.Pool | None = None

# --- Weapon mask mapping ---
mask_for = {
    1:   16,    # SnS
    2:   64,    # DB
    3:    1,    # GS
    4:  128,    # LS
    5:    4,    # Hammer
    6:  256,    # HH
    7:    8,    # Lance
    8:  512,    # GL
    9: 4096,    # Saf
    10: 2048,   # Tonfa
    11: 8192,   # MS
    12:  32,    # LBG
    13:   2,    # HBG
    14: 1024    # Bow
}

weapon_order = list(range(1, 15))
mask_to_name = {
    mask_for[i]: name for i, name in {
        1: "SnS",
        2: "DB",
        3: "GS",
        4: "LS",
        5: "Hammer",
        6: "HH",
        7: "Lance",
        8: "GL",
        9: "Saf",
        10: "Tonfa",
        11: "MS",
        12: "LBG",
        13: "HBG",
        14: "Bow",
    }.items()
}
ALL_KNOWN_MASK = sum(mask_for.values())

# --- Timezone config ---
TZ_NAME = os.getenv("FEATURES_TZ", "America/New_York")
try:
    EASTERN = ZoneInfo(TZ_NAME)
except ZoneInfoNotFoundError:
    raise RuntimeError(
        f"IANA timezone '{TZ_NAME}' not found. On Windows, run: `pip install tzdata` "
        "inside your virtual environment, then restart the bot."
    )

ANCHOR_HOUR = int(os.getenv("FEATURES_HOUR", "23"))  # 11 PM Eastern

def decode_feature_mask(value: int) -> list[str]:
    names = []
    for i in weapon_order:
        m = mask_for[i]
        if value & m:
            names.append(mask_to_name[m])
    return names

def mask_leftovers(value: int) -> int:
    return value & ~ALL_KNOWN_MASK

def unix_for_eastern_anchor(db_ts) -> int:
    """Anchor to ANCHOR_HOUR Eastern on the DB date (DST-aware)."""
    if db_ts is None:
        return int(datetime.now(tz=timezone.utc).timestamp())

    if isinstance(db_ts, str):
        try:
            db_dt = datetime.fromisoformat(db_ts.replace(" ", "T").replace("Z", "+00:00"))
        except Exception:
            db_dt = datetime.strptime(db_ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    elif isinstance(db_ts, datetime):
        db_dt = db_ts
    else:
        db_dt = datetime.now(tz=timezone.utc)

    if db_dt.tzinfo is None:
        db_dt = db_dt.replace(tzinfo=timezone.utc)

    eastern_date = db_dt.astimezone(EASTERN).date()

    eastern_anchored = datetime(
        eastern_date.year, eastern_date.month, eastern_date.day,
        ANCHOR_HOUR, 0, 0, tzinfo=EASTERN
    )
    return int(eastern_anchored.timestamp())

def fmt_time_for_discord(db_ts) -> str:
    unix = unix_for_eastern_anchor(db_ts)
    return f"<t:{unix}:F> (<t:{unix}:R>)"

async def init_db_pool():
    global pool
    pool = await asyncpg.create_pool(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        database=PG_DATABASE,
        min_size=1,
        max_size=5,
        command_timeout=10
    )

@bot.event
async def on_ready():
    global pool
    if pool is None:
        try:
            await init_db_pool()
            print(f"DB pool established. Logged in as {bot.user} (ID: {bot.user.id})")
        except Exception as e:
            print("Failed to create DB pool:", e)
    else:
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

async def fetch_latest_features(limit: int = 3):
    if pool is None:
        raise RuntimeError("Database pool not initialized.")
    sql = """
        SELECT start_time, featured
        FROM feature_weapon
        ORDER BY start_time DESC
        LIMIT $1;
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, limit)
        return rows

def build_features_embed(rows):
    # Reverse so earliest is first
    rows = list(reversed(rows))

    embed = discord.Embed(
        title="Latest Featured Weapons",
        description=f"Times are anchored to {ANCHOR_HOUR}:00 Eastern, auto-converted per viewer.",
        color=discord.Color.blurple()
    )
    for idx, row in enumerate(rows, start=1):
        start_time = row["start_time"]
        featured_raw = row["featured"]

        try:
            featured_val = int(featured_raw) if featured_raw is not None else 0
        except Exception:
            featured_val = 0

        names = decode_feature_mask(featured_val)
        leftovers = mask_leftovers(featured_val)

        lines = [
            f"**start_time:** {fmt_time_for_discord(start_time)}",
            f"**featured (raw):** `{featured_val}`",
            f"**weapons:** {', '.join(names) if names else '—'}",
        ]
        if leftovers:
            lines.append(f"_unknown bits:_ `0x{leftovers:X}`")

        embed.add_field(
            name=f"#{idx}",
            value="\n".join(lines),
            inline=False
        )
    return embed

# ---- Prefix command ----
@bot.command(name="features", aliases=["af"])
async def features_cmd(ctx: commands.Context):
    try:
        rows = await fetch_latest_features(limit=3)
        if not rows:
            await ctx.reply("No entries found in `features_weapon`.")
            return
        embed = build_features_embed(rows)
        await ctx.reply(embed=embed)
    except Exception as e:
        print("Error in !features:", e)
        await ctx.reply("Something went wrong fetching/decoding the latest features. Check logs for details.")

# ---- Slash command ----
@tree.command(name="features", description="Show the latest featured weapons from the database.")
@app_commands.describe(limit="How many latest entries to fetch (default: 3)")
async def slash_features(interaction: discord.Interaction, limit: int = 3):
    try:
        rows = await fetch_latest_features(limit=limit)
        if not rows:
            await interaction.response.send_message("No entries found in `features_weapon`.", ephemeral=True)
            return
        embed = build_features_embed(rows)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        print("Error in /features:", e)
        await interaction.response.send_message(
            "Something went wrong fetching/decoding the latest features.",
            ephemeral=True
        )

def main():
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()