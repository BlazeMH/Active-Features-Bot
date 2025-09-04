# MHF-Z Featured Weapons Discord Bot

A lightweight Discord bot that reads the latest “Featured Weapons” from PostgreSQL and posts a clean, timestamped embed. It supports both `!features` (prefix) and `/features` (slash) commands, and automatically localizes times for each viewer using Discord’s timestamp tags—while **anchoring** the shown time to a chosen hour in a chosen timezone (DST-aware).

---

## ✨ Features

- **Slash & Prefix Commands**: `/features` and `!features`
- **Postgres-backed**: Reads from `feature_weapon` table
- **Weapon mask decoding**: Converts bitmasks into readable weapon names
- **DST-aware anchoring**: Always shows the correct time in the chosen timezone
- **Async & fast**: Uses `asyncpg` connection pool
- **Config via `.env`**: Token, DB, timezone, anchor hour

---

## 📦 Requirements

- Python **3.11+** (recommended)
- PostgreSQL **13+**
- If you run on Windows or an environment missing the IANA database, install **tzdata**

### Python packages

```txt
discord.py>=2.3,<3
asyncpg>=0.29,<1
python-dotenv>=1.0,<2
tzdata>=2024.1   # only needed on Windows
```
## 🔧 Configuration

The bot is configured entirely through a `.env` file in the project root.

### Discord
```env
DISCORD_TOKEN=your-bot-token-here

PG_HOST=127.0.0.1
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=yourpassword
PG_DATABASE=postgres
```
### Feature Display Settings

```env
# Timezone to use for anchoring daily features
# Must be a valid IANA timezone string
# Default: America/New_York
FEATURES_TZ=America/New_York

# Hour of day (0–23) to anchor features in the chosen timezone
# Example: 23 = 11:00 PM local time
# Default: 23
FEATURES_HOUR=23

🕒 How it works:
Each start_time from the database is converted into your chosen timezone, then the date is anchored to FEATURES_HOUR.
Example: With FEATURES_TZ=America/New_York and FEATURES_HOUR=23, all features are displayed as if they start at 11:00 PM Eastern on that date (DST-aware).



