from app.gamemaster.llms import llm
from langchain_core.prompts import ChatPromptTemplate


def suggest_game_session():
    template = """
    """

    prompt = ChatPromptTemplate.from_template(template)

    chain = prompt | llm

    response = chain.invoke({"question": "What is LangChain?"})
