from __future__ import annotations

from dataclasses import dataclass, field

from ..agent import DeepSeekAgent
from .patterns import DebateResult, debate, parallel_execute, sequential_pipeline


@dataclass
class TeamMember:
    """A member of an agent team with a specific role."""
    name: str
    role: str                             # e.g. "researcher", "coder", "reviewer"
    system_prompt: str
    model: str | None = None

    def create_agent(self) -> DeepSeekAgent:
        return DeepSeekAgent(
            system_prompt=self.system_prompt,
            model=self.model or "",
            enable_tools=False,
            enable_rag=False,
            enable_long_term_memory=False,
        )


@dataclass
class AgentTeam:
    """Orchestrates a team of agents for collaborative problem-solving.

    Usage::

        team = AgentTeam(
            name="dev_team",
            members=[
                TeamMember("researcher", "researcher", "You research..."),
                TeamMember("coder", "coder", "You write code..."),
                TeamMember("reviewer", "reviewer", "You review code..."),
            ],
        )
        result = team.collaborate("Build a REST API for a todo app")
    """

    name: str = "agent_team"
    members: list[TeamMember] = field(default_factory=list)
    leader_model: str | None = None        # model for the leader/synthesizer

    # ------------------------------------------------------------------
    # High-level entry points
    # ------------------------------------------------------------------
    def collaborate(
        self,
        task: str,
        mode: str = "sequential",
        rounds: int = 2,
    ) -> str:
        """Run the team in one of the supported modes.

        Args:
            task: The overall goal / task description.
            mode: One of 'sequential', 'parallel', 'debate'.
            rounds: For debate mode, number of discussion rounds.
        """
        if mode == "sequential":
            return self._sequential(task)
        if mode == "parallel":
            return self._parallel(task)
        if mode == "debate":
            return self._debate(task, rounds=rounds)
        raise ValueError(f"Unknown collaboration mode: {mode}")

    # ------------------------------------------------------------------
    # Collaboration patterns
    # ------------------------------------------------------------------
    def _sequential(self, task: str) -> str:
        """Pipeline: each member processes the previous member's output.

        Pattern:  Member-1 ? Member-2 ? ... ? Leader (synthesize)
        """
        agents = [m.create_agent() for m in self.members]
        results = sequential_pipeline(agents, task)

        # Leader synthesizes
        leader = self._leader()
        synthesis = leader.ask(
            f"Synthesize the following results from team members into a final answer.\n\n"
            + "\n\n---\n\n".join(
                f"[{self.members[i].name}] {r}" for i, r in enumerate(results)
            )
            + f"\n\nOriginal task: {task}"
        )
        return synthesis

    def _parallel(self, task: str) -> str:
        """All members work independently on the same task, leader synthesizes."""
        agents = [m.create_agent() for m in self.members]
        results = parallel_execute(agents, task)

        leader = self._leader()
        synthesis = leader.ask(
            f"Synthesize the following independent analyses from team members.\n\n"
            + "\n\n---\n\n".join(
                f"[{self.members[i].name}] {r}" for i, r in enumerate(results)
            )
            + f"\n\nOriginal task: {task}\n\nProvide a comprehensive final answer."
        )
        return synthesis

    def _debate(self, topic: str, rounds: int = 2) -> str:
        """Agents discuss the topic for N rounds, then the leader decides."""
        agents = [m.create_agent() for m in self.members]
        debate_result: DebateResult = debate(agents, topic, rounds=rounds)

        leader = self._leader()
        verdict = leader.ask(
            f"You moderated a debate on: {topic}\n\n"
            + "\n\n".join(
                f"[Round {h['round']}] {h['speaker']}: {h['message']}"
                for h in debate_result.history
            )
            + "\n\nProvide a final verdict synthesizing the best arguments from all sides."
        )
        return verdict

    # ------------------------------------------------------------------
    def _leader(self) -> DeepSeekAgent:
        """Create the leader/synthesizer agent."""
        member_names = ", ".join(m.name for m in self.members)
        return DeepSeekAgent(
            system_prompt=(
                f"You are the leader of team '{self.name}'. Your team members are: {member_names}. "
                "Your role is to synthesize their outputs into a clear, comprehensive final answer. "
                "Resolve any conflicts, fill gaps, and ensure the final output is polished and actionable."
            ),
            model=self.leader_model or "",
            enable_tools=False,
            enable_rag=False,
            enable_long_term_memory=False,
        )
