# wtffmpeg - Natural Language to FFmpeg Translator

## NOTICE, breaking change to command-line options so that they make more sense to someone comfortable in a shell.

- the old `-i` behavior is now the default behavior with no arguments.

This means that now, `wtff` from your command-line will put you in a REPL like a sane person would expect.

- `wtff "some prompt"` will start you in a REPL, but for some reason, you wanted to type the prompt *before hitting return to get into the REPL, so you did this.

I guess it's a safeer landing if you had been passing prompts at the command-line. I've seen videos of people using it like this. (Weird that I've seen videos of people using it at all tbh.) My intent when I made it was to get away from chatui, eliminate all the exposition and verbosity, and just give me the command-line, but with a safety valve of being able to review and edit commands before executing them. Which brings me to...

- If you're on MacOS or Linux, Python (and your login shell too) almost certainly were compiled with libreadline. So now wtffmpeg's REPL uses readline so nobody has to be a savage, or tortured by a CLI.

This means that your up/down arrows from prompt/command history should just work as you expect them to now.a Your left and right arrow too for that matter, which so long as you're in a decent terminal, should mean that you can now easily make edits to your command-line, history, etc. Which brings me to...

- added ~/.wtff_history

So now even between invocations of wtff, your history should be maintained across sessions. This is a good thing because if you aren't wanting to use it one command at a time with -e. -x, or --exec[ute], the expected behavior should be a REPL. Otherwise, you'd just be using a web chaat UI to your preferred LLM, reading the really long answers to how to do something with ffmpeg, and curating/copy/paste between your browser and your shell. wtffmpeg was intended to be a shell interface. 


# WTF? ffmpeg?

`wtffmpeg` is a command-line tool that uses a Large Language Model (LLM) to translate plain English descriptions of video and audio tasks into executable `ffmpeg` commands. It can use local models via Ollama or other OpenAI-compatible APIs, as well as the official OpenAI API.

Stop searching through Stack Overflow and documentation for that one specific `ffmpeg` flag. Just ask for what you want.

**Example:**
```bash
> wtff "convert test_pattern.mp4 to a gif file"

INFO: No API key or LLM_API_URL env var provided. Defaulting to local Ollama at http://localhost:11434
--- Generated ffmpeg Command ---
ffmpeg -i test_pattern.mp4 -vf "fps=10,scale=320:-1:flags=lanczos" output.gif
------------------------------
Execute? [y/N], or (c)opy to clipboard: y

Executing: ffmpeg -i test_pattern.mp4 -vf "fps=10,scale=320:-1:flags=lanczos" output.gif

ffmpeg version n7.0 Copyright (c) 2000-2024 the FFmpeg developers
...
```

## Features
- **Natural Language Interface**: Describe complex `ffmpeg` operations in plain English.
- **Flexible LLM Backend**:
    - **Local First**: Connects to local LLMs like Ollama by default.
    - **Cloud Support**: Easily switch to the OpenAI API or other services using an API key or bearer token.
- **Interactive Execution**: Reviews the generated command before giving you the option to execute it.
- **Clipboard Integration**: Copy commands to your clipboard with a single keypress.
- **Interactive Mode**: Run multiple commands in a persistent session.

## Installation

This script e can use pip or uv pip ses `uv` to manage its dependencies.

1.  **Install `uv`**:
    If you don't have `uv` installed, you can install it with:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.cargo/env" 
    ```

2.  **Clone and Run**:
    The script is designed to be run directly from the cloned repository. `uv` will automatically create a virtual environment and install the required dependencies (`openai` and `pyperclip`) on the first run.
    ```bash
    git clone https://github.com/scottvr/wtffmpeg.git
    cd wtffmpeg
    chmod +x wtffmpeg.py
    ./wtffmpeg.py "your first prompt"
    ```

3.  **Create an Alias (Optional)**:
    For easier access, you can create a symbolic link to the script in a directory that is in your system's `PATH`.
    ```bash
    sudo ln -s "$(pwd)/wtffmpeg.py" /usr/local/bin/wtff
    ```
    Now you can run the tool from anywhere by simply typing `wtff`.

## Configuration

`wtffmpeg` can be configured using command-line arguments or environment variables.

### Environment Variables

You can create a `.env` file in the project directory or export these variables in your shell. An `example.env` file is provided.

-   `WTFFMPEG_MODEL`: The model to use (e.g., `gpt-oss:20b`, `llama3`).
-   `WTFFMPEG_LLM_API_URL`: The base URL for your local LLM API (e.g., `http://localhost:11434`). This is the default connection method if no API key is provided.
-   `WTFFMPEG_OPENAI_API_KEY`: Your API key for the OpenAI service.
-   `WTFFMPEG_BEARER_TOKEN`: A bearer token for authentication with other OpenAI-compatible services.

### Connection Logic

The tool decides which service to use based on the following priority:
1.  If `--api-key` or `WTFFMPEG_OPENAI_API_KEY` is provided, it will connect to the official OpenAI API.
2.  If not, it will look for `--bearer-token` or `WTFFMPEG_BEARER_TOKEN` to authenticate with a custom API endpoint.
3.  If neither of the above is present, it will fall back to using the `--url` or `WTFFMPEG_LLM_API_URL`, defaulting to a local Ollama instance at `http://localhost:11434`.

## Usage

### Command-Line Arguments

```
usage: wtffmpeg.py [-h] [--model MODEL] [--api-key API_KEY] [--bearer-token BEARER_TOKEN] [--url URL] [-x|-e|--exec] [-c] [-i] [prompt]

Translate natural language to an ffmpeg command.

positional arguments:
  prompt                The natural language instruction for the ffmpeg command.  Please note that after the turn for this prompt, you will be dropped back into the REPL. If you only want to execute a single turn, use [-p|--prompt] "prompt". You can further modify the non-REPL behavior with -o [n], -e|x|exec[ute], or -c.

options:
  -h, --help            show this help message and exit
  --model MODEL         The model to use. For Ollama, this should be a model you have downloaded. Defaults to the WTFFMPEG_MODEL env var, then 'gpt-oss:20b'.
  --api-key API_KEY     OpenAI API key. Defaults to WTFFMPEG_OPENAI_API_KEY environment variable.
  --bearer-token BEARER_TOKEN
                        Bearer token for authentication. Defaults to WTFFMPEG_BEARER_TOKEN environment variable.
  --url URL             Base URL for a local LLM API (e.g., http://localhost:11434). Defaults to WTFFMPEG_LLM_API_URL env var, then http://localhost:11434. The '/v1' suffix for OpenAI compatibility will be added automatically.
  -x, -e, --exec         Execute the generated command without confirmation.
  -c, --copy            Copy the generated command to the clipboard.
```

### Examples

**Using the Default Local Ollama Instance:**
```bash
# The tool defaults to http://localhost:11434 and the 'gpt-oss:20b' model
wtff "turn presentation.mov into a web-friendly mp4"
# Note the above is just a way to pre-load context; you will still be dropped into an interactive shell

# Specify a different local model
wtff --model "codellama:7b" -p "extract the audio from lecture.mp4"
# this will not only use the llama-7b model, it will prompt the LLM precisely one time, then exxit, either echoing, ccopying to your clipboard, or executing the command based on your other args, before exiting.
```

**Using the OpenAI API:**
```bash
# The tool will automatically switch to 'gpt-4o' as the default model
export OPENAI_API_KEY="sk-..."
wtff -o  3 -p "create a 10-second clip from movie.mkv starting at the 2 minute mark"
# the above command will output three ways to do what you asked wtffmpeg to do. No ffmpeg command will be executed nor copied to your clipboard. This is just echoing the response (how ever many you specified in the -o # option (default is 1)


# Or provide the key as an argument
wtff --api-key "sk-..." "resize video.mp4 to 720p"
```

## Inside the REPL "interactive" mode.

When in interactive mode, you can type `!` followed by a shell command to execute it directly in your terminal shell. This is useful for listing files (`!ls -l`) or making quick edits.

## TODO (MAYBE):
- add `/` commands from inside the REPL for things like `/chdir /some/new/dir` and have it change your working path wrt the REPL. (Otherwise, `!cd /some/dir` only executes within the context of the spawned shell for the subcommand, which is only useful if you are chaining commands together; doing subshell scripting and is probably not what you expect.) Maybe things like /help, or other non ffmpeg-related interactions you need to have with the REPL or LLM.

# Disclaimer

This was largely made to amuse myself; consider it a piece of humorous performance art but it so borders on being actually useful, I went to the trouble to document all of this. YMMV. Use at your own risk. The author is not responsible for any damage or data loss that may occur from using this tool. Always review generated commands before executing them, especially when working with important files.