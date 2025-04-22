import json


def clean_and_parse_json(llm_response: str) -> dict:
    lines = llm_response.splitlines()
    if lines[0].startswith("`"):
        lines = lines[1:]
    if lines[-1].startswith("`"):
        lines = lines[:-1]
    print("TEST")
    print("\n".join(lines))
    print("TEST")
    return json.loads("\n".join(lines))
