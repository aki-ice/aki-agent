from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from .agent import DeepSeekAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DeepSeek Agent CLI - with Memory, Tools, RAG, Skills, and Team")
    parser.add_argument("message", nargs="*", help="Direct message to the agent")
    parser.add_argument("--system", default="You are a helpful assistant", help="System prompt")
    parser.add_argument("--model", default=None, help="DeepSeek model name")
    parser.add_argument("--no-thinking", action="store_true", help="Disable thinking")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive multi-turn mode")

    # Tools
    parser.add_argument("--no-tools", action="store_true", help="Disable built-in tools")
    parser.add_argument("--max-tool-rounds", type=int, default=5, help="Max tool-calling rounds")

    # RAG
    parser.add_argument("--rag", action="store_true", help="Enable RAG")
    parser.add_argument("--rag-ingest", type=str, default=None, metavar="PATH",
                        help="Ingest a file or directory into RAG store before chatting")
    parser.add_argument("--rag-top-k", type=int, default=5, help="Number of RAG chunks to retrieve")
    parser.add_argument("--rag-store", type=str, default="rag_store.pkl", help="RAG vector store path")

    # Memory
    parser.add_argument("--long-term-memory", action="store_true", help="Enable long-term memory (SQLite)")
    parser.add_argument("--memory-db", type=str, default="memory.db", help="Long-term memory DB path")

    # Skills
    parser.add_argument("--skills-dir", type=str, default=None, help="Directory containing skill YAML/JSON files")

    # Workspace
    parser.add_argument("--workspace", type=str, default=".", help="Workspace root for file tools")
    # Team
    parser.add_argument("--team", action="store_true", help="Run in agent-team collaboration mode")
    parser.add_argument("--team-mode", type=str, default="sequential",
                        choices=["sequential", "parallel", "debate"],
                        help="Team collaboration mode (default: sequential)")
    parser.add_argument("--team-config", type=str, default=None,
                        help="Path to a JSON file defining team members")
    parser.add_argument("--team-rounds", type=int, default=2,
                        help="Debate rounds (default: 2)")
    return parser


def run_interactive(agent: DeepSeekAgent) -> None:
    print("DeepSeek Agent - interactive mode.")
    print("Commands: /exit  /reset  /tools  /rag-search <query>  /memory")
    while True:
        try:
            user_input = input("\nYou > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if not user_input:
            continue
        if user_input == "/exit":
            break
        if user_input == "/reset":
            agent.reset()
            print("[Context cleared]")
            continue
        if user_input == "/tools":
            names = agent.tool_registry.tool_names
            print(f"Available tools: {', '.join(names) if names else '(none)'}")
            continue
        if user_input.startswith("/rag-search "):
            query = user_input[len("/rag-search "):].strip()
            if agent.retriever:
                results = agent.rag_search(query, top_k=5)
                for i, r in enumerate(results, 1):
                    print(f"\n--- Result {i} (score={r['score']}) [{r['title']}] ---")
                    print(r["text"][:300])
            else:
                print("RAG is not enabled. Start with --rag.")
            continue
        if user_input == "/memory":
            if agent.long_term_memory:
                entries = agent.long_term_memory.all()
                if entries:
                    for e in entries[-10:]:
                        print(f"[{e.created_at}] {e.content[:120]}")
                else:
                    print("(no memories yet)")
            else:
                print("Long-term memory is not enabled. Start with --long-term-memory.")
            continue

        answer = agent.ask(user_input)
        print(f"\nAgent > {answer}")


def run_team_mode(args: argparse.Namespace) -> None:
    """Run in agent-team collaboration mode."""
    from .team import AgentTeam, TeamMember

    # Load team config or use defaults
    if args.team_config and os.path.isfile(args.team_config):
        import json
        with open(args.team_config, encoding="utf-8") as fh:
            config = json.load(fh)
        members = [
            TeamMember(
                name=m["name"],
                role=m.get("role", m["name"]),
                system_prompt=m["system_prompt"],
            )
            for m in config.get("members", [])
        ]
    else:
        # Default team: researcher, coder, reviewer
        members = [
            TeamMember(
                name="researcher",
                role="researcher",
                system_prompt=(
                    "You are a thorough researcher. When given a topic: "
                    "1. Identify key aspects and subtopics "
                    "2. Provide factual, well-organized information "
                    "3. Cite sources when possible. Be comprehensive and objective."
                ),
            ),
            TeamMember(
                name="coder",
                role="coder",
                system_prompt=(
                    "You are an expert software engineer. Write clean, well-structured code "
                    "with type hints. Handle edge cases and errors. Prefer standard library."
                ),
            ),
            TeamMember(
                name="reviewer",
                role="reviewer",
                system_prompt=(
                    "You are a code reviewer. Identify bugs, edge cases, security issues. "
                    "Suggest improvements. Be constructive and specific."
                ),
            ),
        ]

    team = AgentTeam(name="default_team", members=members)

    if not args.message:
        print(f"Team mode ({args.team_mode}). Enter your task (Ctrl+C to exit):")
        task = input("\nTask > ").strip()
    else:
        task = " ".join(args.message)

    if not task:
        print("No task provided.")
        return

    print(f"\n[Team] {len(members)} members collaborating in '{args.team_mode}' mode...")
    print(f"  Members: {', '.join(m.name for m in members)}")
    print()

    result = team.collaborate(task, mode=args.team_mode, rounds=args.team_rounds)
    print(result)

def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    agent = DeepSeekAgent(
        system_prompt=args.system,
        model=args.model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        thinking_enabled=not args.no_thinking,
        enable_tools=not args.no_tools,
        enable_rag=args.rag,
        enable_long_term_memory=args.long_term_memory,
        max_tool_rounds=args.max_tool_rounds,
        rag_top_k=args.rag_top_k,
        rag_store_path=args.rag_store,
        memory_db_path=args.memory_db,
        workspace_root=args.workspace,
        skills_dir=args.skills_dir or "",
    )

    # Pre-ingest RAG documents
    if args.rag_ingest and agent.retriever:
        path = args.rag_ingest
        if os.path.isfile(path):
            n = agent.rag_ingest_file(path)
            print(f"[RAG] Ingested {n} chunks from '{path}'")
        elif os.path.isdir(path):
            n = agent.rag_ingest_directory(path)
            print(f"[RAG] Ingested {n} chunks from directory '{path}'")

    # ---- Team mode ----
    if args.team:
        run_team_mode(args)
        return

    # ---- Interactive / one-shot ----
    if args.interactive or not args.message:
        run_interactive(agent)
        return

    message = " ".join(args.message)
    print(agent.ask(message))


if __name__ == "__main__":
    main()
