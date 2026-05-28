import json
import os

transcript_path = r"C:\Users\cakma\sumo\finveri\read_transcript.py"
# Let's overwrite this file to do a deep search on transcript.jsonl
with open(r"C:\Users\cakma\.gemini\antigravity\brain\09956021-6eb2-46e8-a8b7-07e64b56b079\.system_generated\logs\transcript.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total steps in transcript: {len(lines)}")

# We want to find steps in the first 530 steps where USER_INPUT contains "forex", "bist", "aa", or similar keywords, or where plans were described.
for idx, line in enumerate(lines):
    try:
        step = json.loads(line)
        step_idx = step.get("step_index", idx)
        if step_idx >= 530:
            continue
            
        step_type = step.get("type", "")
        content = step.get("content", "")
        
        # Look for user inputs and plans
        if "USER_INPUT" in step_type:
            # Print user inputs
            print(f"--- [USER INPUT] (Step {step_idx}) ---")
            print(content.strip())
            print()
        elif "implementation_plan" in content or "BIST" in content:
            if any(kw in content.lower() for kw in ["forex", "gold", "emtia", "bist30", "yükselenler"]):
                print(f"--- [PLAN/REPLY REFERENCE] (Step {step_idx}) ---")
                print(content[:600].strip() + "\n...[truncated]...")
                print()
    except Exception as e:
        pass
