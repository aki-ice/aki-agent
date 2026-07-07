from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..agent import DeepSeekAgent


@dataclass
class DebateResult:
    topic: str
    history: list[dict[str, Any]] = field(default_factory=list)
    final_positions: list[str] = field(default_factory=list)


def sequential_pipeline(
    agents: list[DeepSeekAgent],
    task: str,
) -> list[str]:
    """Run agents sequentially ? each sees the previous agent's output.

    The first agent gets the raw task; subsequent agents see:
    "Previous output: {prev}\n\nOriginal task: {task}\n\nBuild upon or refine this."
    """
    results: list[str] = []
    carry = task
    for i, agent in enumerate(agents):
        if i == 0:
            output = agent.ask(task)
        else:
            output = agent.ask(
                f"Previous output:\n{carry}\n\n"
                f"Original task: {task}\n\n"
                "Build upon or refine the previous output. Improve it."
            )
        results.append(output)
        carry = output
    return results


def parallel_execute(
    agents: list[DeepSeekAgent],
    task: str,
) -> list[str]:
    """Run all agents independently on the same task."""
    return [agent.ask(task) for agent in agents]


def debate(
    agents: list[DeepSeekAgent],
    topic: str,
    rounds: int = 2,
) -> DebateResult:
    """Agents debate a topic over multiple rounds.

    Each round: all agents see the full debate history and respond.
    """
    result = DebateResult(topic=topic)
    history: list[str] = []

    speaker_names = [f"Agent-{i + 1}" for i in range(len(agents))]

    for rnd in range(1, rounds + 1):
        for i, agent in enumerate(agents):
            if rnd == 1 and not history:
                prompt = (
                    f"Debate topic: {topic}\n\n"
                    "You are the opening speaker. Present your initial position clearly."
                )
            else:
                debate_log = "\n".join(history)
                prompt = (
                    f"Debate topic: {topic}\n\n"
                    f"Debate so far:\n{debate_log}\n\n"
                    "Respond to the previous arguments. "
                    "You may agree, disagree, refine, or present new angles. "
                    "Be concise and substantive."
                )

            response = agent.ask(prompt)
            entry = f"[Round {rnd}] {speaker_names[i]}: {response}"
            history.append(entry)
            result.history.append({
                "round": rnd,
                "speaker": speaker_names[i],
                "message": response,
            })

    # Collect final positions
    for i, agent in enumerate(agents):
        final = agent.ask(
            f"Debate topic: {topic}\n\n"
            + "\n".join(history)
            + "\n\nState your final position in one paragraph."
        )
        result.final_positions.append(final)

    return result
