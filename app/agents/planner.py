from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, Any


PLANNER_PROMPT = ChatPromptTemplate.from_template("""
You are a senior software engineer acting as a planner.

Given a project description, break it down into a clear,
ordered list of development steps.

Project description:
{description}

Return ONLY a numbered list of steps.
""")


def planner_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    # Gemini LLM (lazy initialization)
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        temperature=0
    )

    description = state["user_input"].get("description", "")

    response = llm.invoke(
        PLANNER_PROMPT.format_messages(description=description)
    )

    steps = [
        line.strip("0123456789. ")
        for line in response.content.split("\n")
        if line.strip()
    ]

    state["plan"] = steps
    state["status"] = "completed"
    return state
