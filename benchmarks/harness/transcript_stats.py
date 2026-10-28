"""Count tool calls and failed calls in a subagent transcript, without printing its content.

usage: python transcript_stats.py <agent_transcript.jsonl> [out_json]
"""
import json
import sys
from collections import Counter
from pathlib import Path


def stats(path):
    calls, names, failed, seen_results = Counter(), {}, Counter(), set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        content = (row.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if item.get("type") == "tool_use":
                if item["id"] not in names:
                    calls[item["name"]] += 1
                names[item["id"]] = item["name"]
            elif item.get("type") == "tool_result":
                if item.get("tool_use_id") in seen_results:
                    continue
                seen_results.add(item.get("tool_use_id"))
                text = json.dumps(item.get("content"))
                name = names.get(item.get("tool_use_id"), "?")
                if item.get("is_error") or (name.endswith("fusion_mcp_execute") and '"success": false' in text.replace('\\"', '"')):
                    failed[name] += 1
    execute = sum(v for k, v in calls.items() if k.endswith("fusion_mcp_execute"))
    return {"total_tool_calls": sum(calls.values()), "tool_calls": dict(calls),
            "fusion_execute_calls": execute,
            "fusion_execute_failed": sum(v for k, v in failed.items() if k.endswith("fusion_mcp_execute")),
            "failed_calls_by_tool": dict(failed)}


if __name__ == "__main__":
    result = stats(sys.argv[1])
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
