import json
import logging
import requests

token = json.load(open('config.json'))['slack_token']

def send_notify(text, channel='C07BHEP0CTZ'):
    try:
        slack_result = requests.post(
            "https://slack.com/api/chat.postMessage",
            timeout=10,
            headers={
                "Authorization": token,
                "Content-Type": "application/json;charset=utf-8",
            },
            json={
                "channel": channel,
                "text": text,
            },
        )
        logging.info(f"slack result: {slack_result.status_code}, {slack_result.text}")
    except Exception as e:
        logging.warn(f"failed send slack {e}")

if __name__ == '__main__':
    send_notify('test amm trading')