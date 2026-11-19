import re

def to_slack_mrkdwn(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)          
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.M)   
    text = re.sub(r"^#+\s*", "", text, flags=re.M)          
    return text.strip()

def to_speech_text(text: str) -> str:
    text = re.sub(r"[*_`•]", "", text) 
    return re.sub(r"\s+", " ", text).strip()