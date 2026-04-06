import os
import sys
import argparse
from dotenv import load_dotenv

from src.core.openai_provider import OpenAIProvider
from src.agent.agent import ReActAgent
from src.tools.inventory_tools import INVENTORY_TOOLS
from src.tools.inventory_tools_v2 import INVENTORY_TOOLS_V2
from src.chatbot.chatbot import BaselineChatbot
from src.chatbot.runner import build_provider, run_chat_loop

load_dotenv()

# ── CLI Argument Parser ────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for mode selection."""
    parser = argparse.ArgumentParser(
        description="Lab 3 — Chatbot vs ReAct Agent Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                 # show interactive menu\n"
            "  python main.py --mode chatbot  # run chatbot directly\n"
            "  python main.py --mode agent    # run agent directly\n"
        ),
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["chatbot", "agent"],
        default=None,
        help="Skip menu and run directly in this mode.",
    )
    return parser.parse_args()

# ── Main ───────────────────────────────────────────────────────────────────────

def run_agent_cli() -> None:
    """Run the ReAct agent. VERSION env var selects v1 (default) or v2."""
    version = os.getenv("VERSION", "v1").strip().lower()
    tools = INVENTORY_TOOLS if version == "v1" else INVENTORY_TOOLS_V2

    print(f"=== ReAct Agent CLI [version={version}] ===")
    print("Type 'exit' or 'quit' to stop.\n")

    llm = OpenAIProvider(model_name="gpt-4o-mini")
    agent = ReActAgent(llm=llm, tools=tools, max_steps=5, prompt_version=version)

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            sys.exit(0)

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Bye!")
            break

        response = agent.run(user_input)
        print(f"\nAgent: {response}\n")


def run_chatbot_cli() -> None:
    """Run baseline chatbot flow with provider selected from env / prompt."""
    print("=== Baseline Chatbot CLI ===")
    print("Commands: /history | /reset | /quit\n")

    provider_name = os.getenv("DEFAULT_PROVIDER", "local")

    try:
        llm = build_provider(provider_name)
    except (ValueError, FileNotFoundError) as err:
        print(f"[FATAL] {err}")
        return

    bot = BaselineChatbot(llm=llm)
    # Reuses existing chatbot loop and logger -> still writes to logs/YYYY-MM-DD.log
    run_chat_loop(chatbot=bot, stream=False)


def main() -> None:
    """Main entry point: show menu or dispatch directly to mode."""
    args = parse_args()

    # If mode is specified via CLI, skip the menu and run directly
    if args.mode == "chatbot":
        run_chatbot_cli()
        return
    elif args.mode == "agent":
        run_agent_cli()
        return

    # Otherwise, show interactive menu
    print("=== Main Menu ===")
    print("1) Run Chatbot")
    print("2) Run Agent")
    print("q) Quit\n")

    while True:
        try:
            choice = input("Select option [1/2/q]: ").strip()
        except EOFError:
            # stdin not available (e.g., conda run in non-interactive context)
            print(
                "[INFO] No interactive input available.\n"
                "To run directly, use:\n"
                "  conda run -n ve01 python main.py --mode chatbot\n"
                "  conda run -n ve01 python main.py --mode agent\n"
            )
            sys.exit(0)
        except KeyboardInterrupt:
            print("\nBye!")
            sys.exit(0)

        if choice == "1":
            run_chatbot_cli()
            break
        elif choice == "2":
            run_agent_cli()
            break
        elif choice in ("q", "quit", "exit"):
            print("Bye!")
            return
        else:
            print("Invalid choice. Please enter 1, 2, or q.\n")


if __name__ == "__main__":
    main()