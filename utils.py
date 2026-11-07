from constants import SLACK_BOTS
import random

def get_random_bot():
    return random.choice(SLACK_BOTS)