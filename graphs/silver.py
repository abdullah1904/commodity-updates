from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from firecrawl import Firecrawl
from groq import Groq, RateLimitError
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from utils import to_slack_mrkdwn, to_speech_text
import os, tempfile, logging

load_dotenv()
log = logging.getLogger(__name__)

firecrawl = Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))
groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))


class State(TypedDict, total=False):
    pageContent: str
    slackMessage: str
    is_voice: bool
    audio_path: str


def scrape(state: State) -> State:
    doc = firecrawl.scrape(os.getenv("SILVER_URL"), formats=["markdown"])
    return {"pageContent": (doc.markdown or "")[:12000]}


def generate_message(state: State) -> State:
    prompt = f"""
        You write a personal silver rate update, sent as a direct message to one person in Pakistan.

        Include:
        • Silver: 1 tola only
        • Overall silver trend: up, down, or steady, with change amount or % if shown

        Style:
        - Casual and warm, like a friend giving a quick heads-up
        - Speak to one person ("you"), never to a team or group
        - Start with a short natural opener (vary it, never "Here are today's rates")
        - Then the rate, then 1 plain-words trend sentence
        - Max 5 lines, at most 1-2 emojis
        - No greeting with a name, no mention or tag (added separately)
        - No sign-off, no extra commentary
        - Do NOT mention any date or time
        - Never mention yourself, an AI, a bot, or "I"
        - Avoid words like "delve", "comprehensive", "please note", "team", "everyone", "folks"

        Slack formatting (strict):
        - Bold uses ONE asterisk: *1 Tola*. Never **double asterisks**
        - Bullets use "•" only, never "-" or "*"
        - No headers, tables, links, or code blocks

        Accuracy:
        - Use only numbers found in the content, never invent or calculate
        - Include the currency (PKR) with every price
        - If the silver price is missing, write "Silver: not available right now"
        - If there is no trend, write "Trend: no change data available"

        SILVER CONTENT:
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
            Rewrite this silver rate update as a short spoken script in Urdu, for one person.

            Language:
            - Write ONLY in Urdu script (اردو), natural spoken Pakistani Urdu
            - Not formal or bookish, the way a friend talks on a voice note
            - Currency: say "روپے" instead of PKR
            - Unit: say "تولہ"
            - Silver: "چاندی"

            Style:
            - Warm and casual, like a friend giving a quick heads-up
            - Short sentences, each under 150 characters
            - Max 4 sentences total
            - Cover the silver price (1 tola), then the silver trend
            - End each sentence with "۔"

            Numbers:
            - Write all numbers as Urdu words, e.g. 4500 as "چار ہزار پانچ سو"
            - The value must stay exactly the same, never round, invent, or calculate

            Rules:
            - No emojis, symbols, bullets, asterisks, or English words
            - No greeting with a name, no sign-off
            - Never mention yourself, an AI, or a bot
            - Output only the Urdu script, nothing else

            Silver update (English, for reference):
            {state['slackMessage']}
        """
        res = groq.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        script = to_speech_text(res.choices[0].message.content)

        res = groq.audio.speech.create(
            model="canopylabs/orpheus-arabic-saudi",
            voice="aisha",
            input=to_speech_text(script),
            response_format="wav",
        )
        path = os.path.join(tempfile.gettempdir(), "commodity_rate.wav")
        res.write_to_file(path)
        return {"is_voice": True, "audio_path": path}

    except RateLimitError:
        log.warning("Groq rate limit, skipping silver voice")
        return {"is_voice": False}
    except Exception:
        log.exception("Silver voice generation failed")
        return {"is_voice": False}


def send(state: State) -> State:
    channel = os.getenv("SLACK_CHANNEL_ID")
    text = f'<@{os.getenv("SLACK_USER_ID")}>\n\n{state["slackMessage"]}'

    try:
        client.chat_postMessage(
            channel=channel,
            text=text,
            mrkdwn=True,
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
                filename="silver_rate.wav",
                title="Silver rate voice note",
            )
        except SlackApiError as e:
            log.error("Silver voice upload failed: %s", e.response["error"])
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

silver_workflow = g.compile()

if __name__ == "__main__":
    silver_workflow.invoke({"is_voice": False})