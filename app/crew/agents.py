"""
CrewAI 에이전트 정의 — 교정 리포트용 3종 전문가 에이전트

Sequential Process로 실행:
1. Grammar Agent: 문법/어휘/표현 오류 분석 → corrections[] 반환
2. Expression Agent: 잘 사용한 표현 추출 → new_expressions[] 반환
3. Fluency Agent: 유창성 점수 + 종합 평가 → {fluency_score, summary} 반환

모든 에이전트 공통 설정:
- LLM: openai/gpt-4o (CrewAI 형식 — "provider/model")
- allow_delegation=False: 다른 에이전트에게 위임 불가 (각자 역할 수행)
- verbose=False: 프로덕션 환경에서 불필요한 로그 최소화
"""

from crewai import Agent


def create_grammar_agent(llm_model: str = "openai/gpt-4o") -> Agent:
    """문법/어휘/표현 오류 분석 에이전트. 한국어로 교정 설명 제공."""
    return Agent(
        role="Grammar Correction Specialist",
        goal="Identify and explain all grammar, vocabulary, and expression errors in the learner's utterances",
        backstory=(
            "You are an expert language teacher specializing in grammar analysis for "
            "Korean learners of English and Japanese. You carefully review each learner "
            "utterance and identify errors, providing clear corrections with explanations "
            "in Korean (한국어). You categorize errors by type: grammar, vocabulary, or expression. "
            "You are thorough but fair — only flag genuine errors, not stylistic choices."
        ),
        llm=llm_model,
        verbose=False,
        allow_delegation=False,
    )


def create_expression_agent(llm_model: str = "openai/gpt-4o") -> Agent:
    """표현/어휘 분석 에이전트. 학습자가 잘 사용한 표현을 긍정적으로 강조."""
    return Agent(
        role="Expression and Vocabulary Analyst",
        goal="Identify new or noteworthy expressions the learner used correctly or impressively",
        backstory=(
            "You are a language learning expert who specializes in identifying when learners "
            "use new, advanced, or contextually appropriate expressions. You highlight these "
            "positively to encourage the learner. You provide Korean translations and explain "
            "the context where each expression was used. Focus on expressions that show growth "
            "or good language instinct."
        ),
        llm=llm_model,
        verbose=False,
        allow_delegation=False,
    )


def create_fluency_agent(llm_model: str = "openai/gpt-4o") -> Agent:
    """유창성 평가 에이전트. 1~100 점수 + 한국어 2문장 격려 요약."""
    return Agent(
        role="Fluency Evaluation Expert",
        goal="Evaluate overall conversation fluency and provide an encouraging summary in Korean",
        backstory=(
            "You are a senior language assessment specialist. You evaluate conversational "
            "fluency based on grammar accuracy, vocabulary range, response naturalness, and "
            "contextual appropriateness. You assign a fair score from 1 to 100 and write a "
            "brief (2 sentences), encouraging summary in Korean (한국어). Be honest but supportive."
        ),
        llm=llm_model,
        verbose=False,
        allow_delegation=False,
    )
