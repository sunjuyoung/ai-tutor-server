"""
CrewAI 교정 분석 크루 — 대화 종료 후 비동기 분석 파이프라인

실행 흐름:
1. build_correction_crew() → 3개 에이전트 + 3개 태스크로 Crew 구성
2. run_correction_analysis() → 스레드풀에서 crew.kickoff() 실행 (비동기 래핑)
3. 각 태스크 출력을 JSON으로 파싱 → CorrectionReport 반환

설계 결정:
- Sequential Process: Fluency Agent가 Grammar/Expression 결과를 context로 참조해야 하므로 순차 실행
- run_in_executor: CrewAI의 동기 kickoff()을 asyncio 이벤트루프를 차단하지 않고 실행
- _parse_json_safe: LLM 출력이 순수 JSON이 아닐 수 있으므로 (마크다운 코드블록 등) 다중 파싱 전략 적용
"""

import asyncio
import json
import logging

from crewai import Crew, Process

from app.crew.agents import (
    create_expression_agent,
    create_fluency_agent,
    create_grammar_agent,
)
from app.crew.tasks import (
    create_expression_task,
    create_fluency_task,
    create_grammar_task,
)
from app.schemas.report import CorrectionReport

logger = logging.getLogger(__name__)


def build_correction_crew(conversation_text: str, model: str = "openai/gpt-4o") -> Crew:
    """Build a CrewAI crew for sequential conversation analysis."""
    grammar_agent = create_grammar_agent(model)
    expression_agent = create_expression_agent(model)
    fluency_agent = create_fluency_agent(model)

    grammar_task = create_grammar_task(grammar_agent, conversation_text)
    expression_task = create_expression_task(expression_agent, conversation_text)
    fluency_task = create_fluency_task(fluency_agent, conversation_text)

    # Fluency task gets context from previous tasks
    fluency_task.context = [grammar_task, expression_task]

    return Crew(
        agents=[grammar_agent, expression_agent, fluency_agent],
        tasks=[grammar_task, expression_task, fluency_task],
        process=Process.sequential,
        verbose=False,
    )


async def run_correction_analysis(
    conversation_text: str, model: str = "openai/gpt-4o"
) -> CorrectionReport:
    """Execute the correction crew asynchronously and return structured results."""
    crew = build_correction_crew(conversation_text, model)

    # Run synchronous CrewAI kickoff in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, crew.kickoff)

    # Parse individual task outputs
    grammar_raw = crew.tasks[0].output.raw if crew.tasks[0].output else "[]"
    expression_raw = crew.tasks[1].output.raw if crew.tasks[1].output else "[]"
    fluency_raw = crew.tasks[2].output.raw if crew.tasks[2].output else "{}"

    corrections = _parse_json_safe(grammar_raw, [])
    new_expressions = _parse_json_safe(expression_raw, [])
    fluency_data = _parse_json_safe(fluency_raw, {"fluency_score": 50, "summary": ""})

    # Handle case where fluency_data is a list (shouldn't be, but defensive)
    if isinstance(fluency_data, list):
        fluency_data = fluency_data[0] if fluency_data else {"fluency_score": 50, "summary": ""}

    return CorrectionReport(
        corrections=corrections if isinstance(corrections, list) else [],
        new_expressions=new_expressions if isinstance(new_expressions, list) else [],
        fluency_score=int(fluency_data.get("fluency_score", 50)),
        summary=fluency_data.get("summary", ""),
    )


def _parse_json_safe(raw: str, default):
    """Safely parse JSON from CrewAI agent output, handling markdown blocks."""
    if not raw:
        return default

    # Try direct JSON parse
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try to extract JSON from markdown code blocks
    for marker in ["```json", "```"]:
        if marker in raw:
            parts = raw.split(marker)
            if len(parts) > 1:
                json_str = parts[1].split("```")[0].strip()
                try:
                    return json.loads(json_str)
                except (json.JSONDecodeError, TypeError):
                    pass

    # Try to find JSON array or object in the raw text
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start_idx = raw.find(start_char)
        end_idx = raw.rfind(end_char)
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(raw[start_idx : end_idx + 1])
            except (json.JSONDecodeError, TypeError):
                pass

    logger.warning("Failed to parse JSON from crew output: %s", raw[:200])
    return default
