"""
Project Aura - Curriculum Scheduler for Self-Play SWE-RL

Implements curriculum learning strategies for progressive difficulty
ramping in agent training, preventing catastrophic forgetting while
maximizing skill acquisition.

Reference: Meta FAIR "Self-play SWE-RL" (arXiv:2512.18552), Section 5

Key Features:
- Progressive difficulty ramping based on performance
- Balanced sampling across difficulty levels
- Catastrophic forgetting prevention via replay
- Skill transfer validation across bug types
- Adaptive curriculum based on learning velocity

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
GitHub Issue: #165
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.services.ssr.higher_order_queue import HigherOrderBug

logger = logging.getLogger(__name__)


class CurriculumStrategy(Enum):
    """Curriculum learning strategies."""

    LINEAR = "linear"  # Gradual linear increase
    EXPONENTIAL = "exponential"  # Exponential ramp-up
    ADAPTIVE = "adaptive"  # Based on performance
    SELF_PACED = "self_paced"  # Agent-driven difficulty
    MIXED = "mixed"  # Combination of strategies


class LearningPhase(Enum):
    """Phases of curriculum learning."""

    WARMUP = "warmup"  # Initial easy examples
    RAMPING = "ramping"  # Progressive difficulty increase
    PLATEAU = "plateau"  # Stable difficulty for consolidation
    CHALLENGE = "challenge"  # High difficulty challenges
    REVIEW = "review"  # Review of previously mastered skills


@dataclass
class SkillProfile:
    """Profile of agent skills by bug type."""

    bug_type: str
    solve_rate: float = 0.0  # Overall solve rate
    recent_solve_rate: float = 0.0  # Recent solve rate (last 50)
    total_attempts: int = 0
    successful_solves: int = 0
    avg_attempts_to_solve: float = 0.0
    mastery_level: int = 0  # 0-10 mastery
    last_practiced: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def update(self, solved: bool, attempts: int) -> None:
        """Update skill profile after a solve attempt."""
        self.total_attempts += 1
        if solved:
            self.successful_solves += 1

        self.solve_rate = self.successful_solves / self.total_attempts
        self.last_practiced = datetime.now(timezone.utc)

        # Update mastery level (0-10)
        if self.total_attempts >= 10:
            self.mastery_level = min(10, int(self.solve_rate * 10))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "bug_type": self.bug_type,
            "solve_rate": self.solve_rate,
            "recent_solve_rate": self.recent_solve_rate,
            "total_attempts": self.total_attempts,
            "successful_solves": self.successful_solves,
            "avg_attempts_to_solve": self.avg_attempts_to_solve,
            "mastery_level": self.mastery_level,
            "last_practiced": self.last_practiced.isoformat(),
        }


@dataclass
class CurriculumState:
    """Current state of the curriculum."""

    current_difficulty: int = 1
    current_phase: LearningPhase = LearningPhase.WARMUP
    iterations_in_phase: int = 0
    total_iterations: int = 0
    skill_profiles: dict[str, SkillProfile] = field(default_factory=dict)

    # Performance tracking
    recent_solve_rates: list[float] = field(default_factory=list)  # Last 100
    difficulty_progression: list[tuple[int, float]] = field(default_factory=list)

    # Forgetting prevention
    last_review_difficulty: dict[int, datetime] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "current_difficulty": self.current_difficulty,
            "current_phase": self.current_phase.value,
            "iterations_in_phase": self.iterations_in_phase,
            "total_iterations": self.total_iterations,
            "skill_profiles": {k: v.to_dict() for k, v in self.skill_profiles.items()},
            "recent_solve_rates": self.recent_solve_rates[-100:],
            "difficulty_progression": [
                (d, r) for d, r in self.difficulty_progression[-50:]
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CurriculumState:
        """Deserialize from dictionary."""
        state = cls(
            current_difficulty=data.get("current_difficulty", 1),
            current_phase=LearningPhase(data.get("current_phase", "warmup")),
            iterations_in_phase=data.get("iterations_in_phase", 0),
            total_iterations=data.get("total_iterations", 0),
            recent_solve_rates=data.get("recent_solve_rates", []),
            difficulty_progression=[
                tuple(x) for x in data.get("difficulty_progression", [])
            ],
        )

        # Reconstruct skill profiles
        for key, profile_data in data.get("skill_profiles", {}).items():
            state.skill_profiles[key] = SkillProfile(
                bug_type=profile_data["bug_type"],
                solve_rate=profile_data.get("solve_rate", 0),
                recent_solve_rate=profile_data.get("recent_solve_rate", 0),
                total_attempts=profile_data.get("total_attempts", 0),
                successful_solves=profile_data.get("successful_solves", 0),
                avg_attempts_to_solve=profile_data.get("avg_attempts_to_solve", 0),
                mastery_level=profile_data.get("mastery_level", 0),
            )

        return state


@dataclass
class CurriculumBatch:
    """A batch of bugs selected by the curriculum."""

    bugs: list[HigherOrderBug]
    target_difficulty: int
    phase: LearningPhase
    includes_review: bool = False
    difficulty_distribution: dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "bug_count": len(self.bugs),
            "target_difficulty": self.target_difficulty,
            "phase": self.phase.value,
            "includes_review": self.includes_review,
            "difficulty_distribution": self.difficulty_distribution,
        }


class CurriculumScheduler:
    """
    Curriculum learning scheduler for progressive difficulty ramping.

    This scheduler manages the progression of training difficulty,
    ensuring agents learn progressively harder bugs while preventing
    catastrophic forgetting of previously learned skills.

    Usage:
        scheduler = CurriculumScheduler(strategy=CurriculumStrategy.ADAPTIVE)

        # Get next training batch
        batch = scheduler.get_next_batch(available_bugs, batch_size=32)

        # Update after training
        scheduler.update_performance(solve_rate=0.65, bug_types=["wrong_operator"])

        # Check if curriculum should advance
        if scheduler.should_advance():
            scheduler.advance_curriculum()
    """

    # Phase thresholds
    WARMUP_ITERATIONS = 100
    MIN_SOLVE_RATE_TO_ADVANCE = 0.6
    MAX_SOLVE_RATE_FOR_PLATEAU = 0.8
    REVIEW_INTERVAL_ITERATIONS = 50
    FORGETTING_THRESHOLD = 0.2  # Solve rate drop indicating forgetting

    def __init__(
        self,
        strategy: CurriculumStrategy = CurriculumStrategy.ADAPTIVE,
        initial_difficulty: int = 1,
        max_difficulty: int = 10,
        difficulty_step: int = 1,
        review_ratio: float = 0.2,
    ):
        """
        Initialize the curriculum scheduler.

        Args:
            strategy: Curriculum strategy to use
            initial_difficulty: Starting difficulty level
            max_difficulty: Maximum difficulty level
            difficulty_step: How much to increase difficulty
            review_ratio: Fraction of batch for review items
        """
        self.strategy = strategy
        self.initial_difficulty = initial_difficulty
        self.max_difficulty = max_difficulty
        self.difficulty_step = difficulty_step
        self.review_ratio = review_ratio

        self.state = CurriculumState(
            current_difficulty=initial_difficulty,
            current_phase=LearningPhase.WARMUP,
        )

        # EMA for smooth performance tracking
        self._ema_solve_rate = 0.5
        self._ema_alpha = 0.1

        logger.info(
            f"CurriculumScheduler initialized: strategy={strategy.value}, "
            f"initial_difficulty={initial_difficulty}"
        )

    def get_next_batch(
        self,
        available_bugs: list[HigherOrderBug],
        batch_size: int = 32,
    ) -> CurriculumBatch:
        """
        Get the next training batch based on curriculum state.

        Args:
            available_bugs: List of available bugs to choose from
            batch_size: Target batch size

        Returns:
            CurriculumBatch with selected bugs
        """
        if not available_bugs:
            return CurriculumBatch(
                bugs=[],
                target_difficulty=self.state.current_difficulty,
                phase=self.state.current_phase,
            )

        # Determine target difficulty based on strategy
        target_difficulty = self._calculate_target_difficulty()

        # Select bugs for the batch
        selected_bugs = self._select_bugs(available_bugs, batch_size, target_difficulty)

        # Include review items if needed
        includes_review = False
        if self._should_include_review():
            review_bugs = self._select_review_bugs(
                available_bugs,
                int(batch_size * self.review_ratio),
            )
            selected_bugs = selected_bugs[: batch_size - len(review_bugs)] + review_bugs
            includes_review = bool(review_bugs)

        # Calculate difficulty distribution
        distribution: dict[int, int] = {}
        for bug in selected_bugs:
            distribution[bug.difficulty] = distribution.get(bug.difficulty, 0) + 1

        random.shuffle(selected_bugs)

        return CurriculumBatch(
            bugs=selected_bugs,
            target_difficulty=target_difficulty,
            phase=self.state.current_phase,
            includes_review=includes_review,
            difficulty_distribution=distribution,
        )

    def update_performance(
        self,
        solve_rate: float,
        bug_types: list[str] | None = None,
        solved: bool = False,
        attempts: int = 1,
    ) -> None:
        """
        Update curriculum state after training.

        Args:
            solve_rate: Solve rate for the batch
            bug_types: Bug types in the batch
            solved: Whether the bug was solved (for skill update)
            attempts: Number of attempts taken
        """
        # Update EMA solve rate
        self._ema_solve_rate = (
            self._ema_alpha * solve_rate + (1 - self._ema_alpha) * self._ema_solve_rate
        )

        # Track recent solve rates
        self.state.recent_solve_rates.append(solve_rate)
        if len(self.state.recent_solve_rates) > 100:
            self.state.recent_solve_rates = self.state.recent_solve_rates[-100:]

        # Track difficulty progression
        self.state.difficulty_progression.append(
            (self.state.current_difficulty, solve_rate)
        )

        # Update skill profiles
        if bug_types:
            for bug_type in bug_types:
                if bug_type not in self.state.skill_profiles:
                    self.state.skill_profiles[bug_type] = SkillProfile(
                        bug_type=bug_type
                    )
                self.state.skill_profiles[bug_type].update(solved, attempts)

        # Update iteration counters
        self.state.iterations_in_phase += 1
        self.state.total_iterations += 1

        # Check for phase transitions
        self._check_phase_transition()

    def should_advance(self) -> bool:
        """Check if curriculum should advance to higher difficulty."""
        if self.state.current_difficulty >= self.max_difficulty:
            return False

        if self.state.current_phase == LearningPhase.WARMUP:
            return self.state.iterations_in_phase >= self.WARMUP_ITERATIONS

        if self.state.current_phase in (LearningPhase.RAMPING, LearningPhase.PLATEAU):
            return self._ema_solve_rate >= self.MIN_SOLVE_RATE_TO_ADVANCE

        return False

    def advance_curriculum(self) -> int:
        """
        Advance to the next difficulty level.

        Returns:
            New difficulty level
        """
        old_difficulty = self.state.current_difficulty
        new_difficulty = min(
            self.state.current_difficulty + self.difficulty_step,
            self.max_difficulty,
        )

        self.state.current_difficulty = new_difficulty
        self.state.iterations_in_phase = 0

        # Record when we last practiced this difficulty
        self.state.last_review_difficulty[old_difficulty] = datetime.now(timezone.utc)

        logger.info(
            f"Curriculum advanced: {old_difficulty} -> {new_difficulty}, "
            f"EMA solve rate: {self._ema_solve_rate:.2f}"
        )

        return new_difficulty

    def detect_forgetting(self) -> list[int]:
        """
        Detect if any previously mastered difficulties show forgetting.

        Returns:
            List of difficulty levels showing forgetting
        """
        forgetting_levels = []

        # Check recent performance at each difficulty
        difficulty_performance: dict[int, list[float]] = {}
        for diff, rate in self.state.difficulty_progression[-100:]:
            if diff not in difficulty_performance:
                difficulty_performance[diff] = []
            difficulty_performance[diff].append(rate)

        # Compare recent vs historical performance
        for diff, rates in difficulty_performance.items():
            if len(rates) >= 5:
                recent_avg = sum(rates[-5:]) / 5
                historical_avg = sum(rates[:-5]) / max(len(rates) - 5, 1)

                if historical_avg - recent_avg > self.FORGETTING_THRESHOLD:
                    forgetting_levels.append(diff)
                    logger.warning(
                        f"Forgetting detected at difficulty {diff}: "
                        f"{historical_avg:.2f} -> {recent_avg:.2f}"
                    )

        return forgetting_levels

    def get_skill_gaps(self) -> list[str]:
        """
        Identify bug types with low mastery.

        Returns:
            List of bug types needing more practice
        """
        gaps = []

        for bug_type, profile in self.state.skill_profiles.items():
            if profile.mastery_level < 5 and profile.total_attempts >= 10:
                gaps.append(bug_type)

        return sorted(gaps, key=lambda t: self.state.skill_profiles[t].solve_rate)

    def _calculate_target_difficulty(self) -> int:
        """Calculate target difficulty based on strategy."""
        if self.strategy == CurriculumStrategy.LINEAR:
            return self.state.current_difficulty

        elif self.strategy == CurriculumStrategy.EXPONENTIAL:
            # Exponential ramp based on iterations
            progress = self.state.total_iterations / 1000
            exp_difficulty = int(
                self.initial_difficulty
                + (
                    (self.max_difficulty - self.initial_difficulty)
                    * (1 - math.exp(-progress))
                )
            )
            return max(
                self.initial_difficulty, min(exp_difficulty, self.max_difficulty)
            )

        elif self.strategy == CurriculumStrategy.ADAPTIVE:
            # Adjust based on performance
            if self._ema_solve_rate > 0.7:
                return min(self.state.current_difficulty + 1, self.max_difficulty)
            elif self._ema_solve_rate < 0.4:
                return max(self.state.current_difficulty - 1, self.initial_difficulty)
            return self.state.current_difficulty

        elif self.strategy == CurriculumStrategy.SELF_PACED:
            # Use skill profiles to determine difficulty
            avg_mastery = sum(
                p.mastery_level for p in self.state.skill_profiles.values()
            ) / max(len(self.state.skill_profiles), 1)
            return max(1, min(int(avg_mastery), self.max_difficulty))

        elif self.strategy == CurriculumStrategy.MIXED:
            # Combine adaptive with periodic challenges
            base = self.state.current_difficulty
            if self.state.total_iterations % 100 == 0:
                # Periodic challenge rounds
                return min(base + 2, self.max_difficulty)
            return base

        return self.state.current_difficulty

    def _select_bugs(
        self,
        bugs: list[HigherOrderBug],
        count: int,
        target_difficulty: int,
    ) -> list[HigherOrderBug]:
        """Select bugs for the batch around target difficulty."""
        # Score bugs by how close they are to target difficulty
        scored = []
        for bug in bugs:
            distance = abs(bug.difficulty - target_difficulty)
            score = 1.0 / (1.0 + distance)  # Higher score for closer to target
            scored.append((score, bug))

        # Sort by score and take top
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [bug for _, bug in scored[:count]]

        return selected

    def _select_review_bugs(
        self,
        bugs: list[HigherOrderBug],
        count: int,
    ) -> list[HigherOrderBug]:
        """Select bugs for review of previously mastered difficulties."""
        # Find difficulties we haven't reviewed recently
        review_candidates: dict[int, list[HigherOrderBug]] = {}

        for bug in bugs:
            if bug.difficulty < self.state.current_difficulty:
                if bug.difficulty not in review_candidates:
                    review_candidates[bug.difficulty] = []
                review_candidates[bug.difficulty].append(bug)

        # Prioritize difficulties not reviewed recently
        selected = []
        for diff in sorted(review_candidates.keys()):
            if len(selected) >= count:
                break

            candidates = review_candidates[diff]
            if candidates:
                selected.append(random.choice(candidates))

        return selected

    def _should_include_review(self) -> bool:
        """Check if we should include review items in the batch."""
        # Always include review in later phases
        if self.state.current_phase in (LearningPhase.CHALLENGE, LearningPhase.PLATEAU):
            return True

        # Periodic review during ramping
        if self.state.iterations_in_phase % self.REVIEW_INTERVAL_ITERATIONS == 0:
            return True

        # Include if forgetting detected
        if self.detect_forgetting():
            return True

        return False

    def _check_phase_transition(self) -> None:
        """Check and handle phase transitions."""
        current = self.state.current_phase

        if current == LearningPhase.WARMUP:
            if self.state.iterations_in_phase >= self.WARMUP_ITERATIONS:
                self._transition_to_phase(LearningPhase.RAMPING)

        elif current == LearningPhase.RAMPING:
            if self._ema_solve_rate >= self.MAX_SOLVE_RATE_FOR_PLATEAU:
                self._transition_to_phase(LearningPhase.PLATEAU)
            elif self.state.current_difficulty >= self.max_difficulty:
                self._transition_to_phase(LearningPhase.CHALLENGE)

        elif current == LearningPhase.PLATEAU:
            if self.should_advance():
                self.advance_curriculum()
                self._transition_to_phase(LearningPhase.RAMPING)

        elif current == LearningPhase.CHALLENGE:
            # Check for need to review
            forgetting = self.detect_forgetting()
            if forgetting:
                self._transition_to_phase(LearningPhase.REVIEW)

        elif current == LearningPhase.REVIEW:
            # Return to challenge after review period
            if self.state.iterations_in_phase >= 20:
                self._transition_to_phase(LearningPhase.CHALLENGE)

    def _transition_to_phase(self, new_phase: LearningPhase) -> None:
        """Transition to a new learning phase."""
        old_phase = self.state.current_phase
        self.state.current_phase = new_phase
        self.state.iterations_in_phase = 0

        logger.info(f"Phase transition: {old_phase.value} -> {new_phase.value}")

    def get_metrics(self) -> dict[str, Any]:
        """Get scheduler metrics."""
        return {
            "strategy": self.strategy.value,
            "current_difficulty": self.state.current_difficulty,
            "current_phase": self.state.current_phase.value,
            "iterations_in_phase": self.state.iterations_in_phase,
            "total_iterations": self.state.total_iterations,
            "ema_solve_rate": self._ema_solve_rate,
            "skill_profiles": len(self.state.skill_profiles),
            "avg_mastery": (
                sum(p.mastery_level for p in self.state.skill_profiles.values())
                / max(len(self.state.skill_profiles), 1)
            ),
            "skill_gaps": self.get_skill_gaps(),
            "forgetting_levels": self.detect_forgetting(),
        }

    def reset(self) -> None:
        """Reset the scheduler to initial state."""
        self.state = CurriculumState(
            current_difficulty=self.initial_difficulty,
            current_phase=LearningPhase.WARMUP,
        )
        self._ema_solve_rate = 0.5
        logger.info("Curriculum scheduler reset")
