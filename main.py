import sys
from src.core.openai_provider import OpenAIProvider
from src.agent.agent import ReActAgent
from src.tools.inventory_tools import INVENTORY_TOOLS
from dotenv import load_dotenv

load_dotenv()

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=== ReAct Agent CLI ===")
    print("Type 'exit' or 'quit' to stop.\n")

    llm = OpenAIProvider(model_name="gpt-5.4-mini")
    agent = ReActAgent(llm=llm, tools=INVENTORY_TOOLS, max_steps=5)

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


if __name__ == "__main__":
    main()