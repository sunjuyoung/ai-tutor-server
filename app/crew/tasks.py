from crewai import Agent, Task


def create_grammar_task(agent: Agent, conversation_text: str) -> Task:
    return Task(
        description=(
            f"Analyze the following conversation and identify ALL language errors "
            f"in the learner's messages (marked as [User]). For each error, provide:\n"
            f"- original: the exact text the learner said\n"
            f"- corrected: the correct version\n"
            f"- error_type: one of 'grammar', 'vocabulary', 'expression'\n"
            f"- explanation: brief explanation in Korean (한국어)\n"
            f"- frequency_hint: 1 (first occurrence)\n\n"
            f"Return ONLY a JSON array. If no errors found, return an empty array [].\n\n"
            f"CONVERSATION:\n{conversation_text}"
        ),
        expected_output=(
            'A valid JSON array of correction objects. Example:\n'
            '[{"original": "I go yesterday", "corrected": "I went yesterday", '
            '"error_type": "grammar", "explanation": "과거 시제를 사용해야 합니다", '
            '"frequency_hint": 1}]\n'
            'Return [] if no errors.'
        ),
        agent=agent,
    )


def create_expression_task(agent: Agent, conversation_text: str) -> Task:
    return Task(
        description=(
            f"Analyze the following conversation and identify up to 5 noteworthy expressions "
            f"that the learner (marked as [User]) used correctly or impressively. For each:\n"
            f"- expression: the expression used\n"
            f"- meaning_ko: Korean meaning (한국어)\n"
            f"- context: the conversational context where it was used\n\n"
            f"Return ONLY a JSON array. If no noteworthy expressions, return [].\n\n"
            f"CONVERSATION:\n{conversation_text}"
        ),
        expected_output=(
            'A valid JSON array of expression objects. Example:\n'
            '[{"expression": "That sounds great!", "meaning_ko": "좋은 것 같아요!", '
            '"context": "카페 추천에 대한 긍정적 반응"}]\n'
            'Return [] if none found.'
        ),
        agent=agent,
    )


def create_fluency_task(agent: Agent, conversation_text: str) -> Task:
    return Task(
        description=(
            f"Evaluate the overall fluency of the learner (marked as [User]) in the "
            f"following conversation. Consider grammar accuracy, vocabulary range, "
            f"response naturalness, and contextual appropriateness.\n\n"
            f"Provide:\n"
            f"- fluency_score: integer 1-100\n"
            f"- summary: 2-sentence encouraging evaluation in Korean (한국어)\n\n"
            f"Return ONLY a JSON object with these two fields.\n\n"
            f"CONVERSATION:\n{conversation_text}"
        ),
        expected_output=(
            'A valid JSON object. Example:\n'
            '{"fluency_score": 72, "summary": "자연스러운 대화를 잘 이어나갔어요! '
            '문법 정확도를 조금 더 신경 쓰면 더욱 좋아질 거예요."}'
        ),
        agent=agent,
    )
