# GemmiBot - Local AI Developer Agent

GemmiBot is a Telegram bot that acts as your personal, local AI software engineer. Powered by [Ollama](https://ollama.com/), it guides you through a structured software development lifecycle directly from your Telegram chat, automatically extracting and saving the generated code to your local machine.

## 🚀 Features

* **Structured Development Pipeline**: The bot uses a state-machine workflow to guide you through building a project:
  * **Planning**: Proposes a clean file structure and tech stack.
  * **Development**: Writes full, production-quality code based on the approved plan.
  * **Testing**: Generates test scripts and testing instructions.
  * **Saving & Summary**: Automatically extracts the code from the chat, saves it locally, and provides a final execution guide.
* **Local & Private**: Uses a local instance of Ollama (defaulting to `qwen2.5-coder:1.5b`), ensuring your ideas and code never leave your machine.
* **Smart File Extraction**: Extracts code blocks via custom tags (`<<<FILE: ... >>>`) or smartly parses standard Markdown code blocks and file path comments to rebuild the project locally.
* **Large Message Handling**: Automatically chunks large LLM responses to bypass Telegram's message length limits.
* **Multi-User Support**: Maintains separate session states for different users simultaneously.

## 📋 Prerequisites

Before you begin, ensure you have met the following requirements:
* **Python 3.8+** installed on your machine.
* A **Telegram Bot Token**. You can get one by chatting with [@BotFather](https://t.me/botfather) on Telegram.
* **Ollama** installed and running on your system.

## 🛠️ Local Setup & Installation

**1. Clone the repository**
```bash
git clone [https://github.com/ShaharZohar/GemmiBot.git](https://github.com/yourusername/GemmiBot.git)
cd GemmiBot

2. Set up a Virtual Environment (Recommended)

python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

3. Install Dependencies
The bot requires the python-telegram-bot and ollama Python libraries.

pip install python-telegram-bot ollama

4. Install and Configure Ollama
If you haven't already, download and install Ollama from ollama.com.
Once installed, pull the default language model used by the bot:

ollama pull qwen2.5-coder:1.5b

(Make sure the Ollama app/service is running in the background before starting the bot).

5. Configure the Bot
Open GemmiBot.py in your favorite text editor.
Locate the TELEGRAM_BOT_TOKEN variable and replace the placeholder with your actual bot token:

TELEGRAM_BOT_TOKEN = "YOUR_ACTUAL_BOT_TOKEN_HERE"

(Optional) You can also change the OLLAMA_MODEL variable if you want to use a different model (e.g., llama3 or mistral).

▶️ Running the Bot

Start the bot by running the script:

python GemmiBot.py

ou should see State Machine Bot starting... in your terminal.
📱 How to Use

    Open Telegram and search for your bot's name.

    Send the /start command.

    Send /newproject to initialize the project wizard.

    Follow the prompts:

        Provide a Project Name.

        Provide a Project Description (what you want to build).

    The bot will enter the Planning Stage. Review the proposed architecture.

    If you like the plan, send /approve to move to the Development Stage. (Alternatively, type out adjustments you'd like to make).

    Once the code is generated, type /approve to enter the Testing Stage.

    Type /approve one last time to save all generated files to the ./projects/[Project Name] directory on your local machine and receive a final summary.

    To abort a project at any time, simply type /cancel.

📁 Output Directory

All successfully generated files are saved relative to the directory where the bot is run, under:
./projects/<your_project_name>/
# GemmiBot
