import sys
import subprocess
import pyperclip
from .llm import generate_ffmpeg_command, verify_connection
from .profiles import Profile

from pathlib import Path
CMD_HISTFILE = Path.home() / ".wtff_history"
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
#from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory


def execute_command(command: str) -> int:
    """Execute a shell command, streaming output. Returns exit code."""
    print(f"\nExecuting: {command}\n")
    try:
        with subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        ) as proc:
            if proc.stdout:
                for line in proc.stdout:
                    print(line, end="")
            return proc.wait()
    except Exception as e:
        print(f"Error executing command: {e}", file=sys.stderr)
        return 1


def print_command(cmd: str):
    print("\n--- Generated ffmpeg Command ---")
    print(cmd)
    print("------------------------------")


def single_shot(prompt: str, client: OpenAI, model: str, *, always_copy: bool,  profile: Profile) -> int:
    messages = [
        {"role": "system", "content": profile.text},
        {"role": "user", "content": prompt},
    ]

    raw, cmd = generate_ffmpeg_command(messages, client, model)
    if not cmd:
        print("Failed to generate a command.", file=sys.stderr)
        return 1

    print_command(cmd)

    if cmd and always_copy:
        pyperclip.copy(cmd)
        print("Command copied to clipboard.")

        print("\nExecution cancelled by user.")
        return 0


def repl(preload: str | None, client: OpenAI, model: str, keep_last_turns: int, profile: Profile, always_copy: bool = False):
#    # REPL input history should NOT be persisted (cmd history is separate)
#    session = PromptSession(history=InMemoryHistory(), auto_suggest=AutoSuggestFromHistory())
    def _client_base_url(client) -> str | None:
        for attr in ("base_url", "_base_url"):
            print("d4bug: looking for client attr", attr)
            v = getattr(client, attr, None)
            if v:
                return str(v)
        return None

    session = PromptSession(
        history=FileHistory(str(CMD_HISTFILE)),
        auto_suggest=AutoSuggestFromHistory(),
    )
    messages = [{"role": "system", "content": profile.text}]

    if preload:
        messages.append({"role": "user", "content": preload})    # preload is "safe landing": run once, then drop into repl

        messages = trim_messages(messages, keep_last_turns=keep_last_turns)
        raw, cmd = generate_ffmpeg_command(
            messages, client, model=model
        )
        if cmd:
            messages.append({"role": "assistant", "content": raw})
            messages = trim_messages(messages, keep_last_turns=keep_last_turns)
            print_command(cmd or raw)

    print("Entering interactive mode. Type 'exit'/'quit'/'logout' to leave. Use !<cmd> to run shell commands.")

    while True:
        try:
            line = session.prompt("wtff> ", default=str(prefill) if 'prefill' in locals() else "")
            line = line.strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting interactive mode.")
            return

        if not line:
            continue

        if line in ("exit", "quit", "logout", ":q", ":q!"):
            return
        if line.startswith("/"):
            cmd = line[1:].strip().lower()

            if line in ("/help", "/h", "/?"):
                print("Available /commands:")
                print("  /help, /h, /? - Show this help message")
                print("  /ping - Check LLM connectivity")
                print("  /reset - Clear conversation history (keep system prompt)")
                print("  /profile - Show current profile info")
                print("  /profiles - List available profiles")
                print("  /q|quit|/exit|/logout - Exit the REPL")
                print(" Use !<command> to execute shell commands")
                print("Just type in natural language to generate ffmpeg commands." \
                " Commands are generated on-the-fly and can be edited before execution." \
                " The REPL maintains conversation context, so you can iteratively refine your requests." \
                " For example, start with 'Convert video.mp4 to mp3', then follow up with 'Now make it 128kbps' or 'Actually, I want AAC instead of MP3'." \
                " The system prompt (profile) guides the assistant's behavior. You can switch profiles or customize them to better suit your needs." \
                "")
                continue

            elif cmd in ("ping"):
                try:
                    verify_connection(client, base_url=_client_base_url(client))
                    print("LLM connectivity: OK")
                except RuntimeError as e:
                    print(str(e), file=sys.stderr)
            elif cmd == "reset":
                messages = messages[:1]  # keep system prompt
                print("Conversation history cleared.")
            elif cmd == "profile":
                print(f"Current profile: {profile.name}")
                print(profile.text)
            elif cmd == "profiles":
                avail = list_profiles()
                print("User profiles:")
                for n in avail["user"]:
                    print(f"  {n}")
                print("Built-in profiles:")
                for n in avail["builtin"]:
                    print(f"  {n}")
            else:
                print(f"Unknown command: {line}", file=sys.stderr)
            continue
        if line.startswith("!"):
            shell_cmd = line[1:].strip()
            if shell_cmd:
                rc = execute_command(shell_cmd)
                if rc != 0:
                    print(f"Shell command exited {rc}", file=sys.stderr)
            continue

        messages.append({"role": "user", "content": line})
        messages = trim_messages(messages, keep_last_turns=keep_last_turns)

        raw, cmd = generate_ffmpeg_command(messages, client, model)
        if not cmd:
            print(raw)
            messages.pop()
            continue

        messages.append({"role": "assistant", "content": raw})
        messages = trim_messages(messages, keep_last_turns=keep_last_turns)

        print_command(cmd or raw)
        last_cmd = cmd

        # Stage for next prompt: user can run/edit/clear
        prefill = "!" + " ".join(cmd.splitlines()).strip()


def trim_messages(messages: list[dict], keep_last_turns: int = 12) -> list[dict]:
    if keep_last_turns <= 0:
        # keep only system
        return messages[:1]

    system = messages[0:1]
    rest = messages[1:]
    max_msgs = keep_last_turns * 2
    if len(rest) <= max_msgs:
        return messages
    return system + rest[-max_msgs:]