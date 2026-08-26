from dataclasses import dataclass


REQUIRED_INDEPENDENT_SUCCESSES = 3
LEVEL_SUCCESS_THRESHOLDS = {1: 80, 2: 82, 3: 85, 4: 88, 5: 90}
WEAK_SESSION_THRESHOLD = 45
LEVEL_DOWN_THRESHOLD = 3


@dataclass(frozen=True)
class MasteryState:
    current_level: int
    mastery_percent: int
    independent_streak: int
    struggle_streak: int
    total_plays: int
    is_mastered: bool


@dataclass(frozen=True)
class SessionMetrics:
    played_level: int
    score: int
    correct_answers: int
    total_questions: int
    mistake_count: int
    hints_used: int
    completed: bool


@dataclass(frozen=True)
class MasteryDecision:
    current_level: int
    mastery_percent: int
    independent_streak: int
    struggle_streak: int
    is_mastered: bool
    independent_success: bool
    assisted_success: bool
    level_up: bool
    level_down: bool
    evidence_score: int
    learning_status: str


def success_threshold(level: int) -> int:
    safe_level = max(1, min(level, max(LEVEL_SUCCESS_THRESHOLDS)))
    return LEVEL_SUCCESS_THRESHOLDS[safe_level]


def evaluate_mastery(
    state: MasteryState,
    metrics: SessionMetrics,
    *,
    min_level: int,
    max_level: int,
) -> MasteryDecision:
    """Evaluate durable learning from one completed game session.

    Time is intentionally excluded: processing speed is not learning.
    A session that used hints can train a skill but cannot validate a level.
    """

    attempts = max(
        metrics.correct_answers + metrics.mistake_count,
        metrics.total_questions,
        1,
    )
    first_try_accuracy = round(metrics.correct_answers / attempts * 100)
    evidence = min(metrics.score, first_try_accuracy)
    evidence = max(0, evidence - min(metrics.hints_used * 10, 40))
    if not metrics.completed:
        evidence = min(evidence, 40)

    eligible = metrics.played_level == state.current_level
    threshold = success_threshold(state.current_level)
    independent = metrics.hints_used == 0
    independent_success = (
        eligible
        and metrics.completed
        and independent
        and evidence >= threshold
    )
    assisted_success = (
        eligible
        and metrics.completed
        and not independent
        and metrics.score >= threshold
    )

    # A delayed offline session is kept in history but cannot alter a newer
    # level that was reached before synchronization.
    if not eligible:
        return MasteryDecision(
            current_level=state.current_level,
            mastery_percent=state.mastery_percent,
            independent_streak=state.independent_streak,
            struggle_streak=state.struggle_streak,
            is_mastered=state.is_mastered,
            independent_success=False,
            assisted_success=False,
            level_up=False,
            level_down=False,
            evidence_score=evidence,
            learning_status=learning_status(
                state.mastery_percent,
                state.independent_streak,
                state.is_mastered,
            ),
        )

    mastery_percent = (
        evidence
        if state.total_plays == 0
        else round(state.mastery_percent * 0.65 + evidence * 0.35)
    )
    independent_streak = (
        state.independent_streak + 1 if independent_success else 0
    )
    weak_session = not metrics.completed or evidence < WEAK_SESSION_THRESHOLD
    struggle_streak = state.struggle_streak + 1 if weak_session else 0
    current_level = state.current_level
    is_mastered = state.is_mastered
    level_up = False
    level_down = False

    if independent_streak >= REQUIRED_INDEPENDENT_SUCCESSES:
        if current_level < max_level:
            current_level += 1
            mastery_percent = 0
            independent_streak = 0
            struggle_streak = 0
            is_mastered = False
            level_up = True
        else:
            mastery_percent = 100
            independent_streak = REQUIRED_INDEPENDENT_SUCCESSES
            struggle_streak = 0
            is_mastered = True

    if (
        struggle_streak >= LEVEL_DOWN_THRESHOLD
        and current_level > min_level
        and not level_up
    ):
        current_level -= 1
        mastery_percent = 50
        independent_streak = 0
        struggle_streak = 0
        is_mastered = False
        level_down = True

    return MasteryDecision(
        current_level=current_level,
        mastery_percent=max(0, min(mastery_percent, 100)),
        independent_streak=independent_streak,
        struggle_streak=struggle_streak,
        is_mastered=is_mastered,
        independent_success=independent_success,
        assisted_success=assisted_success,
        level_up=level_up,
        level_down=level_down,
        evidence_score=evidence,
        learning_status=learning_status(
            mastery_percent,
            independent_streak,
            is_mastered,
        ),
    )


def learning_status(
    mastery_percent: int,
    independent_streak: int,
    is_mastered: bool,
) -> str:
    if is_mastered:
        return "mastered"
    if independent_streak >= 2 or mastery_percent >= 75:
        return "consolidating"
    if mastery_percent >= 40:
        return "practicing"
    return "discovering"
