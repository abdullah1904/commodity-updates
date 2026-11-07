from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from firecrawl import Firecrawl
from groq import Groq
from dotenv import load_dotenv
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime
from zoneinfo import ZoneInfo
from utils import get_random_bot

load_dotenv()


firecrawl = Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))
groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

class State(TypedDict):
    bot_name: str
    bot_image: str
    pageContent: str
    slackMessage: str

def scrape(state: State) -> State:
    doc = firecrawl.scrape(os.getenv("GOLD_URL"), formats=["markdown"])
    return {"pageContent": (doc.markdown or "")[:12000], "attempts": 0}

def generate(state: State) -> State:
    prompt = f"""
        You are a friendly Pakistani gold market updater posting in a team Slack channel.
        Write today's gold rate update from the page content below.

        Current Pakistan time: {datetime.now(ZoneInfo("Asia/Karachi")).strftime("%d %b %Y, %I:%M %p PKT")}

        Include:
        - 24 Carat: 1 tola and 1 gram
        - 21 Carat: 1 tola and 1 gram
        - Overall trend: up, down, or steady, with the change amount or % if the content shows it

        Style:
        - Write like a real person, casual and warm, not like a bot or a report
        - Start with a short natural opener (vary it, no "Here are today's rates")
        - 1 trend sentence in plain words, e.g. "Gold is up a bit from yesterday"
        - Slack mrkdwn only: *bold* for the carat labels, bullets for rates
        - At most 1 or 2 emojis, no emoji spam
        - Max 9 lines total, no sign-off, no extra commentary
        - No words like "delve", "comprehensive", "please note"

        Accuracy rules:
        - Use only numbers found in the content, never invent or calculate
        - Use the Pakistan time exactly as given, don't change it
        - Include the currency (PKR)
        - If the content has no trend or previous price, write "Trend: no change data available" instead of guessing

        CONTENT:
        {state['pageContent']}
    """

    res = groq.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return {
        "slackMessage": res.choices[0].message.content.strip(),
    }

def send(state: State) -> State:
    try:
        client.chat_postMessage(
            channel=os.getenv("SLACK_CHANNEL_ID"),
            text=state["slackMessage"],
            username=state['bot_name'],
            icon_url=state['bot_image']
        )
    except SlackApiError as e:
        raise RuntimeError(f"Slack error: {e.response['error']}")
    return {}

g = StateGraph(State)

g.add_node("scrape", scrape)
g.add_node("generate", generate)
g.add_node("send", send)

g.add_edge(START, "scrape")
g.add_edge("scrape", "generate")
g.add_edge("generate", "send")
g.add_edge("send", END)

workflow = g.compile()

if __name__ == "__main__":
    bot = get_random_bot()
    workflow.invoke({
        "bot_name": bot["name"],
        "bot_image": bot["image"],
    })