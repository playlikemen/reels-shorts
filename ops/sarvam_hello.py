#!/usr/bin/env python3.11
"""One Sarvam AI chat completion. Reads SARVAM_API_KEY from the environment or the repo's .env (never printed)."""
import os, pathlib
from sarvamai import SarvamAI

env = pathlib.Path(__file__).resolve().parent.parent / ".env"
if "SARVAM_API_KEY" not in os.environ and env.exists():
    for line in env.read_text().splitlines():
        if line.startswith("SARVAM_API_KEY="):
            os.environ["SARVAM_API_KEY"] = line.split("=", 1)[1].strip()

client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
r = client.chat.completions(model="sarvam-105b",
                            messages=[{"role": "user", "content": "Say hello in Hindi and English in one short line."}])
print(r.choices[0].message.content)
