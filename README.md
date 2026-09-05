# MATRIX AIO

MATRIX AIO is a Python-based Discord bot focused on security, server management, moderation, utilities, and community features.

## Features

- Antinuke protection
- Automoderation
- Moderation tools
- Server configuration
- Welcome system
- Tickets
- Giveaway system
- Leveling
- Self-role system
- Custom roles
- Auto nickname
- Auto reaction
- Autoresponder
- Birthday system
- Voice and VoiceMaster features
- Fun and games
- Server information and utilities
- Logging and tracking
- Discord Components V2 interface
- JSON-based configuration/storage used by several features

## Requirements

- Python 3.10 or newer is recommended
- pip
- A Discord bot application

## Installation

Install the dependencies:

```bash
pip install -r requirements.txt
```

The project currently uses:

- discord.py from the upstream Git repository
- psutil
- python-dotenv

## Configuration

The bot currently stores its main configuration in `config.py`.

Open:

```text
config.py
```

and configure the bot credentials and links.

Example:

```python
class Config:
    TOKEN = "YOUR_BOT_TOKEN_HERE"
    PREFIX = "&"

    BOT_NAME = "MATRIX AIO"
    BOT_VERSION = "2.0.0"

    OWNER_IDS = [YOUR_DISCORD_USER_ID]
    DEVELOPERS = [YOUR_DISCORD_USER_ID]
    DEVELOPER_CREDIT = "r3novadcl"

    INVITE_URL = "https://discord.com/oauth2/authorize?client_id=YOUR_ID"
    SUPPORT_SERVER = "https://discord.gg/YOUR_SUPPORT_SERVER"
    WEBSITE = "https://yourwebsite.com"
    VOTE_URL = "https://top.gg/bot/YOUR_ID"

    BOT_LOGO = "https://your-logo-url.png"

    FOOTER_TEXT = "Powered by FX DEVELOPMENT"
```

Replace all placeholder values before starting the bot.

### Important: Token Security

Do not publish a real Discord token in `config.py`.

For a public GitHub repository, it is strongly recommended to move the token to an environment variable or another secret-management method instead of committing it to source control.

If a real token has already been exposed, regenerate it from the Discord Developer Portal immediately.

## Discord Intents

The current `main.py` uses:

```python
intents = discord.Intents.all()
```

This means the bot requests all available Discord gateway intents.

Depending on the features enabled in the bot, make sure the corresponding privileged intents are enabled in the Discord Developer Portal, especially:

- Server Members Intent
- Message Content Intent
- Presence Intent, if your deployed features actually require it

Only enable privileged intents that your bot needs.

## Start the Bot

From the project directory:

```bash
python main.py
```

If your system uses `python3`:

```bash
python3 main.py
```

A successful startup should load the cogs and log the bot into Discord.

## Project Structure

```text
MATRIX AIO/
├── cogs/
│   ├── antinuke.py
│   ├── automod.py
│   ├── autonick.py
│   ├── autoreact.py
│   ├── autoresponder.py
│   ├── birthday.py
│   ├── configuration.py
│   ├── customrole.py
│   ├── fun.py
│   ├── games.py
│   ├── giveaway.py
│   ├── help.py
│   ├── information.py
│   ├── leveling.py
│   ├── logs.py
│   ├── moderation.py
│   ├── selfrole.py
│   ├── tickets.py
│   ├── tracker.py
│   ├── voice.py
│   ├── voicemaster.py
│   └── welcome.py
├── utils/
│   ├── components.py
│   └── fastconfig.py
├── config.py
├── emojis.py
├── main.py
├── requirements.txt
└── README.md
```

## External Services Used by Utilities

The current code contains utility features that make HTTP requests to public services, including:

- Dog CEO API for the random dog image feature
- QR Server API for QR code generation

Some other utility responses are explicitly demo/placeholder functionality and mention services such as Google Translate and OpenWeather for future integration. They are not configured as required API credentials in the current `config.py`.

## Updating the Bot

After modifying files:

```bash
git add .
git commit -m "Update MATRIX AIO"
git push
```

## Troubleshooting

### `ModuleNotFoundError`

Run:

```bash
pip install -r requirements.txt
```

### Bot does not log in

Check:

- The token in `config.py`
- The Discord application/bot status
- Your internet connection
- Required intents in the Developer Portal

### Cogs fail to load

Run:

```bash
python main.py
```

and read the cog-specific error printed in the terminal. Make sure all files inside `cogs/` are present.

## GitHub Security

Before pushing the project publicly:

- Remove real bot tokens
- Remove private API keys
- Remove passwords and connection strings
- Do not commit private credentials
- Consider adding `.env`, local databases, logs, and Python cache files to `.gitignore`

A public repository should contain placeholders rather than live credentials.

## Credits

**Developer:** r3novadcl  
**Team:** FX DEVELOPMENT

Discord: https://discord.gg/epKhYP6Y74

## Original Project Credits

The current source also contains an existing credit reference to `GACKY AND MATRIX STUDIOS`. current development credit as **FX DEVELOPMENT — r3novadcl**.
