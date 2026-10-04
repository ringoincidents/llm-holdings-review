from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from schemas.api import (
    S1BooleanResult,
    S1ChoiceResult,
    S1RouteInput,
    S1RouteResult,
    S1ScoreResult,
)
from s1.interface import S1Provider, S1State


Transport = Callable[[dict[str, Any]], Mapping[str, Any]]


def _as_probability(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"Clef response has invalid {label}")
    probability = float(value)
    if probability < 0 or probability > 1:
        raise RuntimeError(f"Clef response has invalid {label}")
    return probability


def _distribution(answer: Mapping[str, Any], options: Sequence[str]) -> dict[str, float]:
    raw = answer.get("probabilities", answer.get("distribution"))
    if isinstance(raw, Mapping):
        result = {
            option: _as_probability(raw.get(option, 0.0), label=f"probability:{option}")
            for option in options
        }
        if any(result.values()):
            return result
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)) and len(raw) == len(options):
        return {
            option: _as_probability(raw[index], label=f"probability:{option}")
            for index, option in enumerate(options)
        }
    return {}


@dataclass
class CloudflareClefProvider(S1Provider):
    """Optional Cloudflare Clef adapter behind the Holdings-owned S1 contract.

    Clef is an experimental provider. This class deliberately exposes only S1
    result objects to the Runtime; Cloudflare response shapes stay inside here.
    """

    account_id: str
    auth_token: str
    model: str = "clef-flash"
    timeout_s: float = 15.0
    transport: Transport | None = None
    name: str = field(init=False)

    def __post_init__(self) -> None:
        if self.model not in {"clef", "clef-flash"}:
            raise ValueError("model must be clef or clef-flash")
        if not self.account_id.strip():
            raise ValueError("Cloudflare account_id is required")
        if not self.auth_token.strip():
            raise ValueError("Cloudflare auth_token is required")
        self.name = f"cloudflare-{self.model}"

    def _run(self, state: S1State, questions: Mapping[str, Any]) -> Mapping[str, Any]:
        payload = {
            "model": self.model,
            "state": state,
            "questions": dict(questions),
        }
        if self.transport is not None:
            response_payload = self.transport(payload)
        else:
            endpoint = (
                "https://api.cloudflare.com/client/v4/accounts/"
                f"{self.account_id}/ai/run/@cf/cloudflare/clef"
            )
            try:
                response = httpx.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                    json=payload,
                    timeout=self.timeout_s,
                )
            except httpx.HTTPError as exc:
                raise RuntimeError("Clef request failed") from exc
            if response.status_code < 200 or response.status_code >= 300:
                # Never include the remote response body: it may contain provider
                # diagnostics or user data that does not belong in Runtime errors.
                raise RuntimeError(f"Clef request failed with HTTP {response.status_code}")
            try:
                response_payload = response.json()
            except ValueError as exc:
                raise RuntimeError("Clef returned invalid JSON") from exc

        if not isinstance(response_payload, Mapping):
            raise RuntimeError("Clef returned an invalid response")
        result = response_payload.get("result", response_payload)
        if not isinstance(result, Mapping):
            raise RuntimeError("Clef returned an invalid result")
        answers = result.get("answers")
        if not isinstance(answers, Mapping):
            raise RuntimeError("Clef response missing answers")
        return answers

    @staticmethod
    def _answer(answers: Mapping[str, Any], key: str) -> Mapping[str, Any]:
        answer = answers.get(key)
        if not isinstance(answer, Mapping):
            raise RuntimeError(f"Clef response missing answer:{key}")
        return answer

    def choice(self, state: S1State, choices: Sequence[str]) -> S1ChoiceResult:
        options = list(choices)
        if not options:
            raise ValueError("choices must not be empty")
        answers = self._run(
            state,
            {
                "choice": {
                    "type": "choice",
                    "instructions": "Choose the single best option for this state.",
                    "criteria": {option: option for option in options},
                }
            },
        )
        answer = self._answer(answers, "choice")
        selected = answer.get("choice")
        if selected not in options:
            raise RuntimeError("Clef returned a choice outside the allowed options")
        distribution = _distribution(answer, options)
        raw_confidence = answer.get("confidence")
        if raw_confidence is not None:
            confidence = _as_probability(raw_confidence, label="confidence")
        elif selected in distribution:
            confidence = distribution[selected]
        else:
            raise RuntimeError("Clef choice response missing confidence")
        return S1ChoiceResult(
            choice=str(selected),
            confidence=confidence,
            distribution=distribution or {str(selected): confidence},
            provider=self.name,
        )

    def boolean(self, state: S1State, question: str) -> S1BooleanResult:
        answers = self._run(
            state,
            {"boolean": {"type": "noul", "instructions": question}},
        )
        answer = self._answer(answers, "boolean")
        probability = _as_probability(answer.get("noul"), label="noul probability")
        return S1BooleanResult(
            value=probability >= 0.5,
            probability=probability,
            provider=self.name,
        )

    def score(self, state: S1State, scale: Sequence[str]) -> S1ScoreResult:
        levels = list(scale)
        if not levels:
            raise ValueError("scale must not be empty")
        answers = self._run(
            state,
            {
                "score": {
                    "type": "score",
                    "instructions": "Score this state against the ordered rubric.",
                    "criteria": levels,
                }
            },
        )
        answer = self._answer(answers, "score")
        distribution = _distribution(answer, levels)
        raw_score = answer.get("score")

        if distribution:
            selected = max(levels, key=lambda level: distribution[level])
            confidence = distribution[selected]
        elif isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool):
            index = max(0, min(len(levels) - 1, int(round(float(raw_score)))))
            selected = levels[index]
            confidence = 1.0
            distribution = {level: 1.0 if level == selected else 0.0 for level in levels}
        else:
            raise RuntimeError("Clef score response missing usable score probabilities")

        return S1ScoreResult(
            score=selected,
            confidence=confidence,
            distribution=distribution,
            provider=self.name,
        )

    def route(self, task: S1RouteInput) -> S1RouteResult:
        options = ["research", "review", "developer", "human"]
        state = {
            "company": task.company,
            "title": task.title,
            "risk_level": task.risk_level,
        }
        answers = self._run(
            state,
            {
                "department": {
                    "type": "choice",
                    "instructions": (
                        "Which department should handle this case? Choose human when "
                        "the request itself requires human authorization."
                    ),
                    "criteria": {
                        "research": "Investigate, analyze, gather evidence or study.",
                        "review": "Verify, audit, critique or independently check work.",
                        "developer": "Implement, build, debug, change code or systems.",
                        "human": "Requires explicit human authorization or judgment.",
                    },
                },
                "human_review": {
                    "type": "noul",
                    "instructions": (
                        "Does this case require human review before execution because "
                        "of risk, authority, external side effects or irreversible action?"
                    ),
                },
            },
        )
        department_answer = self._answer(answers, "department")
        department = department_answer.get("choice")
        if department not in options:
            raise RuntimeError("Clef returned a route outside the allowed departments")
        distribution = _distribution(department_answer, options)
        raw_confidence = department_answer.get("confidence")
        if raw_confidence is not None:
            confidence = _as_probability(raw_confidence, label="route confidence")
        elif department in distribution:
            confidence = distribution[department]
        else:
            raise RuntimeError("Clef route response missing confidence")

        review_answer = self._answer(answers, "human_review")
        review_probability = _as_probability(
            review_answer.get("noul"),
            label="human_review probability",
        )
        human_review = review_probability >= 0.5

        # D0/governance safety remains authoritative over D1 probability.
        if task.risk_level in {"high", "critical"} or department == "human":
            human_review = True

        task_type = {
            "research": "research",
            "review": "review",
            "developer": "development",
            "human": "human_review",
        }[str(department)]

        return S1RouteResult(
            company=task.company,
            department=str(department),
            task_type=task_type,
            human_review=human_review,
            confidence=confidence,
            provider=self.name,
        )


def build_s1_provider_from_env(
    env: Mapping[str, str] | None = None,
) -> S1Provider:
    values = env if env is not None else os.environ
    provider = values.get("HOLDINGS_S1_PROVIDER", "rule").strip().lower()
    if provider in {"", "rule", "rule-s1", "rule-s1-v0"}:
        from s1.providers.rule import RuleS1Provider

        return RuleS1Provider()
    if provider not in {"clef", "clef-flash"}:
        raise ValueError(f"Unsupported HOLDINGS_S1_PROVIDER: {provider}")
    account_id = values.get("CLOUDFLARE_ACCOUNT_ID", "")
    auth_token = values.get("CLOUDFLARE_AUTH_TOKEN", "")
    if not account_id or not auth_token:
        raise RuntimeError(
            "Clef provider requires CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_AUTH_TOKEN"
        )
    return CloudflareClefProvider(
        account_id=account_id,
        auth_token=auth_token,
        model=provider,
    )
