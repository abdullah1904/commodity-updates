from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from firecrawl import Firecrawl
from groq import Groq
from dotenv import load_dotenv
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from utils import get_random_bot, to_slack_mrkdwn, to_speech_text
import tempfile

load_dotenv()


firecrawl = Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))
groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

class State(TypedDict):
    bot_name: str
    bot_image: str
    pageContent: str
    slackMessage: str 
    is_voice: bool
    audio_path: str   

def scrape(state: State) -> State:
    doc = firecrawl.scrape(os.getenv("GOLD_URL"), formats=["markdown"])
    return {"pageContent": (doc.markdown or "")[:12000], "attempts": 0}

def generate_message(state: State) -> State:
    prompt = f"""
        You write a personal gold rate update, sent as a direct message to one person in Pakistan.

        Include:
        • 24 Carat: 1 tola and 1 gram
        • 21 Carat: 1 tola and 1 gram
        • Overall trend: up, down, or steady, with change amount or % if shown

        Style:
        - Casual and warm, like a friend giving a quick heads-up
        - Speak to one person ("you"), never to a team or group
        - Start with a short natural opener (vary it, never "Here are today's rates")
        - Then the rates, then 1 plain-words trend sentence
        - Max 8 lines, at most 1-2 emojis
        - No greeting with a name, no mention or tag (added separately)
        - No sign-off, no extra commentary
        - Do NOT mention any date or time
        - Never mention yourself, an AI, a bot, or "I"
        - Avoid words like "delve", "comprehensive", "please note", "team", "everyone", "folks"

        Slack formatting (strict):
        - Bold uses ONE asterisk: *24 Carat*. Never **double asterisks**
        - Bullets use "•" only, never "-" or "*"
        - No headers, tables, links, or code blocks

        Accuracy:
        - Use only numbers found in the content, never invent or calculate
        - Include the currency (PKR) with every price
        - If there is no trend or previous price, write "Trend: no change data available"

        CONTENT:
        {state['pageContent']}
    """

    res = groq.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return {"slackMessage": to_slack_mrkdwn(res.choices[0].message.content)}

def generate_voice(state: State) -> State:
    try:
        prompt = f"""
        Rewrite this gold rate update as a short spoken script for one person.
        - Warm, casual, like a friend
        - Short sentences, each under 150 characters
        - Say "rupees" instead of "PKR", write out numbers naturally
        - No emojis, symbols, or extra commentary
        - Keep every number exactly as given

        TEXT:
        {state['slackMessage']}
        """
        res = groq.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        script = to_speech_text(res.choices[0].message.content)

        res = groq.audio.speech.create(
            model="canopylabs/orpheus-v1-english",
            voice="diana",
            input=to_speech_text(script),
            response_format="wav",
        )
        path = os.path.join(tempfile.gettempdir(), "gold_rate.wav")
        res.write_to_file(path)
        return {"is_voice": True, "audio_path": path}

    except groq.RateLimitError:
        return {"is_voice": False}
    except Exception as e:
        return {"is_voice": False}
        

def send(state: State) -> State:
    channel = os.getenv("SLACK_CHANNEL_ID")
    text = f'<@{os.getenv("SLACK_USER_ID")}>\n\n{state["slackMessage"]}'

    try:
        msg = client.chat_postMessage(
            channel=channel,
            text=text,
            mrkdwn=True,
            username=state["bot_name"],
            icon_url=state["bot_image"],
            unfurl_links=False,
            unfurl_media=False,
        )
    except SlackApiError as e:
        raise RuntimeError(f"Slack error: {e.response['error']}")

    if state.get("is_voice"):
        try:
            client.files_upload_v2(
                channel=channel,
                file=state["audio_path"],
                filename="gold_rate.wav",
                title="Gold rate voice note",
                thread_ts=msg["ts"],
            )
        except SlackApiError as e:
            pass
    return {}

g = StateGraph(State)

g.add_node("scrape", scrape)
g.add_node("generate_message", generate_message)
g.add_node("generate_voice", generate_voice)
g.add_node("send", send)

g.add_edge(START, "scrape")
g.add_edge("scrape", "generate_message")
g.add_edge("generate_message", "generate_voice")
g.add_edge("generate_voice", "send")
g.add_edge("send", END)

workflow = g.compile()

if __name__ == "__main__":
    bot = get_random_bot()
    workflow.invoke({
        "bot_name": bot["name"],
        "bot_image": bot["image"],
    })