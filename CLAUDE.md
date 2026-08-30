# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-server Turkish-language Discord bot ("Vassal of Tiamat" / Heavenly Court). Every
feature is meant to be reconfigured live from inside Discord via slash commands — there is
no config file to edit for day-to-day operation. All runtime state lives in a local SQLite
database and survives restarts.

## Commands

```bash
pip install -r requirements.txt          # discord.py, python-dotenv, aiohttp
python bot.py                             # run the bot (needs DISCORD_TOKEN in .env)
```

- No build step, no test suite, no linter configured.
- `.env` must contain `DISCORD_TOKEN=...` (see `.env.example`). `load_dotenv()` also reads
  a real environment variable, so hosting platforms can inject it directly.
- Deploy targets: Discloud (`discloud.config`), Square Cloud (`squarecloud.config`), and a
  generic `Procfile` (`worker: python bot.py`). All run it as a **background worker**, not a
  web service — there is no HTTP server or health-check port.

## Architecture

Two source files:

- **`config.py`** — immutable defaults only. `AUTO_RESPONSES` (built-in trigger→replies map)
  and `WELCOME_MESSAGE` / `LEAVE_MESSAGE` / `*_GIF` strings. The `DEFAULT_*_CHANNEL_ID`
  constants let an operator hard-code channel IDs so a fresh deploy isn't blank.
- **`bot.py`** — everything else: persistence layer, Discord event handlers, all slash
  commands, and the role-menu UI components.

### Persistence (`bot.py` top section)

- `bot_data` is a **single module-level dict**, loaded once at import via `load_data()`.
  Handlers mutate it in place and must call `save_data(bot_data)` afterward to persist.
- Storage is a local SQLite file `bot_data.db`, one row per top-level key, values are
  `json.dumps` text. `load_data()` merges `DEFAULT_DATA` for any missing/`None` key and
  one-time-imports a legacy `bot_data.json` if the DB is empty.
- **Why SQLite and not JSON/cloud KV:** Discord snowflake IDs are 64-bit ints. The previous
  JSONBin backend stored them as JS float64 and silently rounded them, so saved channel IDs
  stopped matching real channels and games appeared "broken." Keep IDs as ints/strings
  through text storage — never round-trip them through anything float-based. See the comment
  block around `_get_db()`.

### Message handling — order matters

`on_message` is one function with a fixed priority chain; each stage `return`s if it handles
the message, so earlier stages win:

1. **Kelime Türetmece** (Turkish word-chain game) — only in `word_game_channel_id`. Validates
   against the TDK dictionary API (`sozluk.gov.tr`, 3s timeout; on network failure falls back
   to a length/alpha heuristic). Enforces last-letter linking, no-repeat, and the anti-solo
   rule (same user can't play twice in a row). Words ending in `ğ` grant +10 and reset the round.
2. **Sayı Saymaca** (counting game) — only in `count_game_channel_id`. Sequential ints from 1,
   same anti-solo rule, wrong number resets to 1.
3. **Auto-responses** — `config.AUTO_RESPONSES` merged with `bot_data["custom_responses"]`
   (custom overrides built-in by key). `wildcard: True` = substring match, else exact match.
   Picks randomly among a trigger's `responses` list.
4. `bot.process_commands` for prefix (`!`) commands — currently none defined.

### Channel resolution

- Welcome/leave channel: saved ID first, then fuzzy name match (`avlu`, `giriş`, `welcome`,
  …), then `system_channel`, then first text channel. See `get_welcome_channel`.
- Game channels: **saved ID only**, no fuzzy fallback — `is_word_game_channel` /
  `is_count_game_channel` return `False` when unset, so games are off until an admin runs the
  start command in a channel.

### Role menus

- `DynamicRoleSelect` / `DynamicRoleMenuView` — built from admin-supplied role names/IDs
  (`/ozel_rol_menusu`), resolves via `get_role_by_identifier` (ID or name).
- `FixedRoleSelect` — hard-coded option lists for the `/rol_menusu` presets (renk / muzik /
  ilgi). Option `label`s must exactly equal existing Discord role names; selecting toggles
  the role.
### Persistent views across restarts

All role-menu views are `timeout=None` with **stable** `custom_id`s
(`vassal:dynamic_role_select`, `interest_exact`, `color_exact`, `music_exact`). Two layers
keep already-posted menus alive after a restart:

1. `setup_hook` calls `self.add_view(...)` once per menu type as a generic fallback keyed by
   `custom_id` (covers legacy fixed menus not in the DB).
2. Every posted menu is recorded in `bot_data["role_menus"]`
   (`channel_id` / `message_id` / `kind` / `roles_data`) by `remember_role_menu()`.
   `restore_role_menus()` (also in `setup_hook`) rebuilds each view and re-binds it to its
   exact `message_id`, pruning entries it can't rebuild.

Dynamic menus don't need their role list stored to *function* — the callback resolves roles
live from the select's submitted values — but `roles_data` is persisted so the view rebuilds
with the right `max_values`. Menus posted before this system existed (random `custom_id`s)
stay dead and must be reposted.

### Memory (target: run under ~256 MB free hosting)

`RAM=100` OOM-killed the process with no traceback (silent restart loop). Discloud's free
100 MB tier is too small for Python + discord.py regardless of tuning — deploy on a panel
host giving ≈256 MB. The bot is tuned to run in ~90–150 MB:

- `intents` is built from `Intents.none()` — only `guilds`, `members`, `guild_messages`,
  `message_content`.
- `VassalBot` passes `max_messages=None` (no message cache), `chunk_guilds_at_startup=False`,
  `member_cache_flags=MemberCacheFlags.none()`. **Consequence:** `guild.get_member()` almost
  always returns `None`; never rely on the member cache. `on_member_join` / `on_member_remove`
  still get a full `Member` from the event payload, and interaction handlers get one from the
  interaction. Leaderboards render users as raw `<@id>` strings (mention without a cache hit).
- One shared `aiohttp.ClientSession` (`bot.session`, opened in `setup_hook`, closed in
  `close()`) instead of a session per TDK lookup.
- `word_game_used_words` capped at 500 entries.

`discloud.config` `RAM=100` (Discloud free cap) / `squarecloud.config` `MEMORY=256`.
`.env` (gitignored) holds `DISCORD_TOKEN`; on a GitHub deploy it must be set as a panel env var.

### Conventions

- All slash commands are Turkish-named and gated with
  `@app_commands.checks.has_permissions(administrator=True)` except the public read-only ones
  (`skor_tablosu`, `sayi_rekoru`).
- Every command body is wrapped in `try/except` that reports the error back as an ephemeral
  message; most `defer(ephemeral=True)` first.
- User-facing text is Turkish. Keep it that way.
- `setup_hook` calls `self.tree.sync()` globally on every start — new/renamed commands can
  take up to an hour to propagate.
