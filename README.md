# Open Blueberry

A Discord bot with autonomous AI agent capabilities, inspired by OpenClaw. Uses Ollama for AI interactions and provides multi-step task execution with tool use.

## Features

- **Agentic Task Execution**: Break down complex tasks into steps and execute them autonomously
- **Code Generation & Execution**: Generate and run Python or Bash scripts on demand
- **Conversational AI**: Chat with memory and context awareness
- **Tool Integration**: Execute shell commands, read/write files, list directories
- **Discord Integration**: Seamless bot commands for various operations

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/trishantpahwa/open-blueberry.git
    cd open-blueberry
    ```

2. Create and activate virtual environment:

    ```bash
    python3 -m venv env
    source env/bin/activate
    ```

3. Install dependencies:

    ```bash
    pip install discord.py aiohttp python-dotenv
    ```

4. Set up environment variables:
   Create a `.env` file with:

    ```
    DISCORD_BOT_TOKEN=your_discord_bot_token
    OLLAMA_API_URL=http://localhost:11434
    OLLAMA_MODEL=qwen3-coder-next:cloud
    SCRIPT_DIR=./scripts
    ```

5. Ensure Ollama is running with the specified model.

## Usage

### Commands

- `!task <description>` - Execute complex tasks with multi-step reasoning
- `!auto_execute <language> "<description>"` - Generate and execute code directly
- `!chat <message>` - Have a conversation with the AI
- `!clear` - Clear conversation memory
- `!status` - Check bot status
- `!info` - Show help information

### Examples

```
!task Install requests library and write a script to fetch data from an API
!auto_execute python "Calculate fibonacci numbers"
!chat What tasks can you help me automate?
```

## Configuration

The bot can be configured via environment variables:

- `DISCORD_BOT_TOKEN`: Your Discord bot token
- `OLLAMA_API_URL`: Ollama API endpoint (default: http://localhost:11434)
- `OLLAMA_MODEL`: Ollama model to use (default: qwen3-coder-next:cloud)
- `SCRIPT_DIR`: Directory for generated scripts (default: ./scripts)

## Requirements

- Python 3.9+
- Discord.py
- aiohttp
- python-dotenv
- Ollama with compatible model

## License

See LICENSE file.
