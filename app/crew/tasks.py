"""
CrewAI 태스크 정의 — 대화 분석용 3종 태스크

각 태스크는 대화 텍스트 + 시나리오 맥락을 받아서 분석을 수행하고,
엄격한 JSON 포맷으로 결과를 반환한다.

태스크별 역할:
1. Grammar Task: 오류 찾기 → corrections[] (최대 10건)
2. Expression Task: 잘 쓴 표현 → new_expressions[] (최대 5건)
3. Fluency Task: 종합 평가 → {fluency_score, summary}

시나리오 컨텍스트:
- scenario_title, scenario_goal을 제공하여 시나리오 달성도까지 평가
- 예: "카페 주문" 시나리오에서 주문 관련 표현을 잘 사용했는지 평가
"""

from crewai import Agent, Task


def create_grammar_task(
    agent: Agent,
    conversation_text: str,
    language: str = "en",
    scenario_title: str = "",
    scenario_goal: str = "",
    difficulty: int = 1,
) -> Task:
    """
    문법/어휘/표현 오류 분석 태스크.

    학습 언어와 난이도에 따라 분석 깊이를 조절:
    - difficulty 1: 기본 문법 오류만 지적, 설명을 쉽게
    - difficulty 2: 중급 문법 + 표현 오류, 대안 표현 제시
    - difficulty 3: 고급 뉘앙스, 문체, 경어 오류까지 분석
    """
    # 난이도별 분석 지침
    difficulty_guide = {
        1: "초급 학습자입니다. 의미 전달에 영향을 주는 핵심 오류만 지적하세요. 사소한 오류는 무시해도 됩니다. 설명은 쉽고 짧게.",
        2: "중급 학습자입니다. 문법 오류 + 어색한 표현도 교정하세요. 더 자연스러운 대안 표현을 함께 제시해주세요.",
        3: "고급 학습자입니다. 뉘앙스, 문체 일관성, 격식 수준까지 세밀하게 분석하세요. 원어민이 사용하는 자연스러운 표현과의 차이점을 설명해주세요.",
    }.get(difficulty, "중급 학습자입니다. 문법 오류 + 어색한 표현도 교정하세요.")

    # 언어별 error_type 가이드
    if language == "ja":
        error_type_guide = (
            "error_type 분류 기준 (일본어):\n"
            "  - 'grammar': 조사 오류, 동사/형용사 활용 실수, 문장 구조 오류, 경어 체계 혼란\n"
            "  - 'vocabulary': 단어 선택 오류, 한국어 직역, 카타카나 오용, 유의어 혼동\n"
            "  - 'expression': 부자연스러운 표현, 상황에 맞지 않는 격식 수준, 관용적이지 않은 문장"
        )
        example_output = (
            '[{"original": "昨日友達を会いました", "corrected": "昨日友達に会いました", '
            '"error_type": "grammar", "explanation": "「会う」는 \'に\'와 함께 사용합니다. '
            '\'を\'는 타동사의 목적어에 사용하지만, 「会う」는 자동사이므로 조사 \'に\'가 맞습니다.", '
            '"frequency_hint": 1}]'
        )
    else:
        error_type_guide = (
            "error_type 분류 기준 (영어):\n"
            "  - 'grammar': 시제 오류, 관사 누락/오용, 주어-동사 일치, 전치사 오류, 어순 실수\n"
            "  - 'vocabulary': 단어 선택 오류, 한국어 직역, 가산/불가산 혼동, 연어(collocation) 오류\n"
            "  - 'expression': 부자연스러운 표현, 격식 수준 부적절, 관용적이지 않은 문장, 어색한 구어체"
        )
        example_output = (
            '[{"original": "I go to cafe yesterday", "corrected": "I went to a cafe yesterday", '
            '"error_type": "grammar", "explanation": "두 가지 오류가 있습니다: '
            '(1) 과거를 나타내는 yesterday가 있으므로 동사를 과거형 went로 바꿔야 합니다. '
            '(2) cafe는 가산명사이므로 관사 a가 필요합니다.", '
            '"frequency_hint": 1}]'
        )

    # 시나리오 컨텍스트 (있으면 추가)
    scenario_context = ""
    if scenario_title:
        scenario_context = (
            f"\n시나리오 정보:\n"
            f"- 제목: {scenario_title}\n"
            f"- 학습 목표: {scenario_goal}\n"
            f"- 이 시나리오에서 자주 필요한 표현과 관련된 오류에 특히 주의하세요.\n"
        )

    return Task(
        description=(
            f"아래 대화에서 학습자([User])의 발화만 분석하여 언어 오류를 찾아주세요.\n"
            f"AI([AI])의 발화는 분석 대상이 아닙니다.\n\n"
            f"분석 난이도 지침: {difficulty_guide}\n"
            f"{scenario_context}\n"
            f"{error_type_guide}\n\n"
            f"각 오류에 대해 다음 필드를 포함하는 JSON 객체를 작성하세요:\n"
            f"- original: 학습자가 실제로 말한 텍스트 (오류가 포함된 부분만 발췌)\n"
            f"- corrected: 올바르게 교정한 버전\n"
            f"- error_type: 'grammar' | 'vocabulary' | 'expression'\n"
            f"- explanation: 왜 틀렸고 어떻게 고쳐야 하는지 한국어로 설명 (2-3문장)\n"
            f"- frequency_hint: 이 대화에서 같은 유형의 오류가 반복된 횟수 (1 이상)\n\n"
            f"규칙:\n"
            f"- 같은 문장에 여러 오류가 있으면 가장 중요한 것부터 별도 항목으로 분리\n"
            f"- 같은 유형의 반복 오류는 대표 1건만 남기고 frequency_hint를 높여주세요\n"
            f"- 최대 10건까지만 반환 (가장 중요한 순서대로)\n"
            f"- 오류가 없으면 빈 배열 []을 반환\n"
            f"- 반드시 유효한 JSON 배열만 출력하세요. 다른 텍스트를 포함하지 마세요.\n\n"
            f"CONVERSATION:\n{conversation_text}"
        ),
        expected_output=(
            f"A valid JSON array of correction objects. Example:\n"
            f"{example_output}\n"
            f"Return [] if no errors found."
        ),
        agent=agent,
    )


def create_expression_task(
    agent: Agent,
    conversation_text: str,
    language: str = "en",
    scenario_title: str = "",
    scenario_goal: str = "",
    difficulty: int = 1,
) -> Task:
    """
    학습자가 잘 사용한 표현 추출 태스크.

    시나리오 맥락을 고려하여, 해당 상황에서 특히 적절했던 표현을
    우선적으로 선택한다.
    """
    if language == "ja":
        example_output = (
            '[{"expression": "お会計お願いします", '
            '"meaning_ko": "계산 부탁합니다", '
            '"context": "레스토랑에서 식사를 마친 후 자연스럽게 계산을 요청하는 상황에서 사용. '
            '「お会計」는 격식 있는 표현으로, 식당에서의 매너를 보여줍니다. '
            '캐주얼한 상황에서는 「チェックお願いします」도 사용 가능합니다."}]'
        )
    else:
        example_output = (
            '[{"expression": "Could I get a latte to go?", '
            '"meaning_ko": "라떼 테이크아웃으로 주세요", '
            '"context": "카페 주문 상황에서 \'Could I get...\' 패턴을 정확하게 사용했습니다. '
            '\'Can I have...\' 보다 한 단계 정중한 표현이고, '
            '\'to go\'는 테이크아웃을 뜻하는 자연스러운 미국식 표현입니다. '
            '영국식으로는 \'takeaway\'를 사용합니다."}]'
        )

    # 시나리오 컨텍스트
    scenario_context = ""
    if scenario_title:
        scenario_context = (
            f"\n시나리오 정보:\n"
            f"- 제목: {scenario_title}\n"
            f"- 학습 목표: {scenario_goal}\n"
            f"- 이 시나리오의 목표와 관련된 표현은 특히 높이 평가하세요.\n"
        )

    return Task(
        description=(
            f"아래 대화에서 학습자([User])가 사용한 표현 중 칭찬할 만한 것을 "
            f"최대 5개 선별하세요.\n\n"
            f"선별 기준 (우선순위 높은 것부터):\n"
            f"1. 시나리오 상황에 딱 맞는 적절한 표현\n"
            f"2. 학습자 수준 대비 인상적인 어휘/구문 사용\n"
            f"3. 자연스러운 구어체, 관용구, 연결 표현\n"
            f"4. 이전에 틀렸다가 이번에 올바르게 사용한 표현\n"
            f"5. 원어민이 자주 사용하는 자연스러운 반응/맞장구\n"
            f"{scenario_context}\n"
            f"각 표현에 대해 다음 JSON 필드를 포함하세요:\n"
            f"- expression: 학습자가 사용한 원문 표현\n"
            f"- meaning_ko: 한국어 의미 + 뉘앙스 설명\n"
            f"- context: 이 표현이 왜 좋았는지, 어떤 상황에서 재사용할 수 있는지 "
            f"한국어로 상세 설명 (2-3문장)\n\n"
            f"규칙:\n"
            f"- 너무 기본적인 표현(Yes, No, Thank you 등)은 초급자가 아닌 한 제외\n"
            f"- 학습자 수준이 낮을수록 기본 표현도 긍정적으로 평가\n"
            f"- 칭찬할 표현이 없으면 빈 배열 []을 반환\n"
            f"- 반드시 유효한 JSON 배열만 출력하세요.\n\n"
            f"CONVERSATION:\n{conversation_text}"
        ),
        expected_output=(
            f"A valid JSON array of expression objects (max 5). Example:\n"
            f"{example_output}\n"
            f"Return [] if no noteworthy expressions."
        ),
        agent=agent,
    )


def create_fluency_task(
    agent: Agent,
    conversation_text: str,
    language: str = "en",
    scenario_title: str = "",
    scenario_goal: str = "",
    difficulty: int = 1,
) -> Task:
    """
    유창성 종합 평가 태스크.

    Grammar Task와 Expression Task의 결과를 context로 참조하여,
    오류 수/심각도와 좋은 표현 사용을 종합적으로 반영한 점수를 매긴다.
    """
    # 시나리오 컨텍스트
    scenario_context = ""
    if scenario_title:
        scenario_context = (
            f"\n시나리오 정보:\n"
            f"- 제목: {scenario_title}\n"
            f"- 학습 목표: {scenario_goal}\n"
            f"- 시나리오 달성도도 평가에 반영하세요 (목표를 달성했는가?).\n"
        )

    if language == "ja":
        level_reference = "JLPT N1(90+) ~ N5(~20) 수준을 참고"
    else:
        level_reference = "CEFR C2(90+) ~ A1(~20) 수준을 참고"

    return Task(
        description=(
            f"아래 대화에서 학습자([User])의 전반적인 유창성을 종합 평가하세요.\n\n"
            f"이전 분석 결과(Grammar corrections, Expression highlights)를 반드시 참고하여 "
            f"일관된 평가를 하세요.\n"
            f"{scenario_context}\n"
            f"평가 기준 (총 100점, {level_reference}):\n"
            f"1. 문법 정확성 (30점): 오류 빈도와 심각도. 의미 전달 방해 오류는 큰 감점.\n"
            f"2. 어휘 다양성 (20점): 같은 단어 반복 vs 다양한 표현 사용.\n"
            f"3. 대화 자연스러움 (25점): 응답이 맥락에 맞는지, 흐름이 자연스러운지.\n"
            f"4. 시나리오 달성도 (15점): 주어진 상황의 목표를 수행했는가.\n"
            f"5. 의사소통 적극성 (10점): 질문하기, 대화 확장, 의견 표현 시도.\n\n"
            f"반환 형식:\n"
            f"- fluency_score: 1~100 정수\n"
            f"- summary: 한국어 2문장\n"
            f"  - 첫 문장: 구체적으로 잘한 점 칭찬 (예: '카페 주문 표현을 정확하게 사용했어요!')\n"
            f"  - 둘째 문장: 다음에 시도해볼 개선 포인트 1가지 (예: '다음에는 과거 시제에 좀 더 신경 써보세요.')\n\n"
            f"주의사항:\n"
            f"- 점수는 공정하게. 짧은 대화라도 품질이 좋으면 높은 점수 가능.\n"
            f"- 오류가 많더라도 의사소통에 성공했으면 최소 30점 이상.\n"
            f"- 반드시 유효한 JSON 객체만 출력하세요.\n\n"
            f"CONVERSATION:\n{conversation_text}"
        ),
        expected_output=(
            'A valid JSON object with exactly two fields. Example:\n'
            '{"fluency_score": 68, "summary": "카페에서 주문 표현을 정확하게 사용하고 '
            '추가 질문도 자연스럽게 했어요! 다음에는 과거 시제(went, had)를 좀 더 '
            '연습해보면 대화가 한층 자연스러워질 거예요."}'
        ),
        agent=agent,
    )
