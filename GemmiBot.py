import logging
import os
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ollama import AsyncClient

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# CONFIGURATION
TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
OLLAMA_MODEL = "qwen2.5-coder:1.5b"
BASE_PROJECTS_DIR = os.path.abspath("./projects")

# Project State Store
user_sessions = {}

# SYSTEM PROMPTS FOR EACH STAGE
SYSTEM_PROMPT = (
    "You are an expert software engineer assistant. You build clean, production-ready code. "
    "Always follow the guidelines specified in the system stage instructions."
)

STAGE_INSTRUCTIONS = {
    "PLANNING": (
        "\n[SYSTEM INSTRUCTION: We are in the PLANNING STAGE. Do not write implementation code yet. "
        "Propose a clean file structure and tech stack for the project. Ask the user for approval or feedback.]"
    ),
    "DEVELOPMENT": (
        "\n[SYSTEM INSTRUCTION: We are in the DEVELOPMENT STAGE. Implement the approved plan. "
        "Write full, production-quality code. You MUST wrap every file you want saved in this exact tag format:\n"
        "<<<FILE: relative/path/to/file.ext>>>\n"
        "[Insert file contents here]\n"
        "<<<END_FILE>>>\n"
        "Ensure all modules are fully implemented. Do not skip or truncate files.]"
    ),
    "TESTING": (
        "\n[SYSTEM INSTRUCTION: We are in the TESTING STAGE. Provide instructions on how to test the generated code. "
        "Create test scripts or unit tests if necessary, wrapping any new test files in the <<<FILE:...>>> tags. "
        "Ask the user to test and report any bugs or type /approve to finalize.]"
    ),
    "SUMMARY": (
        "\n[SYSTEM INSTRUCTION: We are in the SUMMARY STAGE. Write a final project summary "
        "and clear step-by-step execution guide on how to install dependencies and run the application.]"
    )
}

def sanitize_name(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name.strip())

def extract_and_save_files(text: str, project_dir: str) -> list:
    """Parses custom tags and falls back to Markdown blocks with comment paths to write files."""
    saved_files = []
    
    # --- Strategy 1: Look for exact custom tags <<<FILE: path >>> ---
    pattern_custom = re.compile(r'<<<FILE:\s*(.*?)>>>\s*(.*?)\s*<<<END_FILE>>>', re.DOTALL)
    matches = pattern_custom.findall(text)
    
    if matches:
        os.makedirs(project_dir, exist_ok=True)
        for filepath, content in matches:
            filepath = filepath.strip()
            target_path = os.path.abspath(os.path.join(project_dir, filepath))
            if not target_path.startswith(os.path.abspath(project_dir)):
                logger.warning(f"Skipped unsafe filepath: {filepath}")
                continue
                
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content.strip())
            saved_files.append(filepath)
        return saved_files

    # --- Strategy 2: Fallback to Markdown code blocks ---
    block_pattern = re.compile(r'```(?:\w+)?\n(.*?)\n```', re.DOTALL)
    matches_iter = list(block_pattern.finditer(text))
    
    for match in matches_iter:
        content = match.group(1).strip()
        start_pos = match.start()
        
        lines = content.split('\n')
        first_line = lines[0].strip() if lines else ""
        
        filepath = None
        
        # A) Check if the first line of the code block is a file path comment:
        # Matches: # main.py or // src/index.js or /* config.json */
        comment_pattern = re.compile(r'^(?:#|//|/\*)\s*([\w\-./\\]+\.\w+)\s*(?:\*/)?$')
        comment_match = comment_pattern.match(first_line)
        if comment_match:
            filepath = comment_match.group(1).strip()
            # Remove the filepath comment from the actual file body
            content = '\n'.join(lines[1:]).strip()
        else:
            # B) Look at preceding non-empty lines in text right before the code block
            preceding_text = text[:start_pos]
            preceding_lines = [l.strip() for l in preceding_text.split('\n') if l.strip()]
            if preceding_lines:
                # Inspect last 3 lines to locate a string that looks like a file name
                for line in reversed(preceding_lines[-3:]):
                    # Strip common markdown headers/styling: **, *, ###, `
                    cleaned_line = re.sub(r'[*#`\-]', '', line).strip()
                    # Match name patterns: e.g. path/to/filename.ext
                    if re.match(r'^[\w\-./\\]+\.\w+$', cleaned_line):
                        filepath = cleaned_line
                        break
                        
        if filepath:
            filepath = filepath.strip()
            target_path = os.path.abspath(os.path.join(project_dir, filepath))
            # Verify file is destined within the sandbox path limits
            if not target_path.startswith(os.path.abspath(project_dir)):
                logger.warning(f"Skipped unsafe filepath: {filepath}")
                continue
                
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content.strip())
            saved_files.append(filepath)
            
    return list(set(saved_files))

async def safe_send(update: Update, text: str, parse_mode: str = None) -> None:
    try:
        await update.message.reply_text(text, parse_mode=parse_mode)
    except Exception:
        await update.message.reply_text(text)

async def send_large_message(update: Update, text: str, parse_mode: str = None) -> None:
    MAX_LENGTH = 4000
    if len(text) <= MAX_LENGTH:
        await safe_send(update, text, parse_mode)
        return

    lines = text.split('\n')
    current_chunk = []
    current_length = 0
    
    for line in lines:
        if len(line) > MAX_LENGTH:
            if current_chunk:
                await safe_send(update, '\n'.join(current_chunk), parse_mode)
                current_chunk = []
                current_length = 0
            
            for i in range(0, len(line), MAX_LENGTH):
                await safe_send(update, line[i:i+MAX_LENGTH], parse_mode)
            continue

        if current_length + len(line) + 1 > MAX_LENGTH:
            await safe_send(update, '\n'.join(current_chunk), parse_mode)
            current_chunk = [line]
            current_length = len(line)
        else:
            current_chunk.append(line)
            current_length += len(line) + 1
            
    if current_chunk:
        await safe_send(update, '\n'.join(current_chunk), parse_mode)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to the Local Dev Agent!\n\n"
        "To start a new software project, run /newproject\n"
        "To abort or reset at any time, run /cancel"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_sessions.pop(user_id, None)
    await update.message.reply_text("Project wizard canceled. Send /newproject to start over.")

async def new_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_sessions[user_id] = {
        "name": "",
        "desc": "",
        "stage": "GET_NAME",
        "history": [{"role": "system", "content": SYSTEM_PROMPT}],
        "last_code_output": ""
    }
    await update.message.reply_text("Let's build a new project! What is the name of your project?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_text = update.message.text

    if user_id not in user_sessions:
        await update.message.reply_text("Please run /newproject to begin.")
        return

    session = user_sessions[user_id]
    stage = session["stage"]

    if stage == "GET_NAME":
        session["name"] = sanitize_name(user_text)
        session["stage"] = "GET_DESC"
        await update.message.reply_text(
            f"Project name set to `{session['name']}`.\n\n"
            f"Now, please describe what you want this project to do. What are the requirements and features?"
        )
        return

    elif stage == "GET_DESC":
        session["desc"] = user_text
        session["stage"] = "PLANNING"
        await update.message.reply_text("Setting up requirements and building a project plan...")
        
        setup_context = (
            f"User wants to build a project named '{session['name']}'. "
            f"Description and requirements:\n{session['desc']}"
        )
        session["history"].append({"role": "user", "content": setup_context + STAGE_INSTRUCTIONS["PLANNING"]})
        await process_ollama_call(update, context, session)
        return

    if user_text.strip().lower() == "/approve":
        await advance_stage(update, context, session)
    else:
        session["history"].append({"role": "user", "content": user_text + STAGE_INSTRUCTIONS[session["stage"]]})
        await process_ollama_call(update, context, session)

async def advance_stage(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict) -> None:
    current_stage = session["stage"]

    if current_stage == "PLANNING":
        session["stage"] = "DEVELOPMENT"
        await update.message.reply_text("Plan Approved! Now entering the **Development Stage** (generating files)...")
        session["history"].append({
            "role": "user", 
            "content": "I approve the plan. Please write the complete files now." + STAGE_INSTRUCTIONS["DEVELOPMENT"]
        })
        await process_ollama_call(update, context, session)

    elif current_stage == "DEVELOPMENT":
        session["stage"] = "TESTING"
        await update.message.reply_text("Code Approved! Now entering the **Testing Stage**...")
        session["history"].append({
            "role": "user", 
            "content": "I approve the code. Please generate testing instructions and test scripts." + STAGE_INSTRUCTIONS["TESTING"]
        })
        await process_ollama_call(update, context, session)

    elif current_stage == "TESTING":
        session["stage"] = "SAVING"
        project_dir = os.path.join(BASE_PROJECTS_DIR, session["name"])
        await update.message.reply_text(f"Compiling project. Writing files to: `{project_dir}`...")

        compiled_files = []
        for msg in session["history"]:
            if msg["role"] == "assistant":
                saved = extract_and_save_files(msg["content"], project_dir)
                compiled_files.extend(saved)

        compiled_files = list(set(compiled_files))

        if compiled_files:
            file_list_str = "\n".join([f"- `{f}`" for f in compiled_files])
            await update.message.reply_text(f"Successfully saved files to disk:\n{file_list_str}")
        else:
            await update.message.reply_text(
                "No files detected in standard extraction tags or fallback markdown blocks.\n\n"
                "Please make sure your generated code has standard markdown backticks "
                "with a file path header above them, or a comment containing the file path on the first line."
            )

        session["stage"] = "SUMMARY"
        await update.message.reply_text("Generating project usage guide...")
        session["history"].append({
            "role": "user", 
            "content": "All files saved successfully. Please summarize how to run and use the project." + STAGE_INSTRUCTIONS["SUMMARY"]
        })
        await process_ollama_call(update, context, session)

    elif current_stage == "SUMMARY":
        user_id = update.effective_user.id
        await update.message.reply_text("Development process completed! Enjoy your application.")
        user_sessions.pop(user_id, None)

async def process_ollama_call(update: Update, context: ContextTypes.DEFAULT_TYPE, session: dict) -> None:
    """Invokes local Ollama instance and sends reply back to Telegram."""
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # 1. Ask Ollama for completion
    try:
        client = AsyncClient()
        response = await client.chat(
            model=OLLAMA_MODEL,
            messages=session["history"]
        )

        if hasattr(response, 'message'):
            reply = response.message.content
        elif isinstance(response, dict):
            reply = response.get('message', {}).get('content', '')
        else:
            reply = str(response)

    except Exception as e:
        logger.error(f"Error querying Ollama API: {e}")
        await update.message.reply_text(
            "An error occurred while contacting Ollama. Please ensure your Ollama service is active."
        )
        return

    # 2. Add response to session memory (original, un-chunked)
    session["history"].append({"role": "assistant", "content": reply})

    # 3. Handle footers and split message delivery
    stage = session["stage"]
    footer = ""
    
    if stage == "PLANNING":
        footer = "\n\n💡 *Type your feedback to revise, or send /approve to enter Development Stage.*"
    elif stage == "DEVELOPMENT":
        footer = "\n\n💡 *Type adjustments to make, or send /approve to enter Testing Stage.*"
    elif stage == "TESTING":
        footer = "\n\n💡 *Type bug reports/fixes, or send /approve to save files and summarize.*"
    elif stage == "SUMMARY":
        footer = "\n\n💡 *Send /approve to close this session and finish.*"

    full_reply = reply + footer

    # Send chunked message stream
    try:
        await send_large_message(update, full_reply, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error transmitting messages: {e}")
        await update.message.reply_text("The generated response could not be fully transmitted over the Telegram API.")

def main() -> None:
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("Set your actual Telegram bot token inside the script.")
        return

    # Build bot with generous connection parameters
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("newproject", new_project))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("approve", handle_message)) 
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("State Machine Bot starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
