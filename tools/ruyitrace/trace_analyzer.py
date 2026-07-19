"""Parse ruyiTrace NDJSON output, extract fingerprint API calls by category.

The custom DOMTrace runtime can emit one known malformed shape when a long
Function source is followed by the ``typeof`` result field.  The analyzer keeps
the raw defect visible, applies only an unambiguous structural repair in memory,
and reports any line that remains unrecoverable.

Usage:
    python trace_analyzer.py <trace.ndjson> [--category canvas|webgl|audio|all]
                             [--json] [--strict]
"""

import argparse
import json
from collections import defaultdict


FUNCTION_SOURCE_REPAIR_REASON = "typeof-function-source-closing-quote"
FUNCTION_SOURCE_BAD_BOUNDARY = '\\"},"result":"function","stack":'

CATEGORIES = {
    "canvas":    ["CanvasRenderingContext2D", "HTMLCanvasElement", "OffscreenCanvas",
                  "toDataURL", "toBlob", "getImageData", "createImageBitmap"],
    "webgl":     ["WebGLRenderingContext", "WebGL2RenderingContext",
                  "getParameter", "getExtension", "getShaderPrecisionFormat",
                  "getSupportedExtensions", "getContextAttributes"],
    "audio":     ["AudioContext", "OfflineAudioContext", "AnalyserNode",
                  "AudioBuffer", "OscillatorNode", "createAnalyser",
                  "getByteFrequencyData", "getFloatFrequencyData"],
    "webrtc":    ["RTCPeerConnection", "RTCDataChannel", "createDataChannel",
                  "createOffer", "createAnswer", "setLocalDescription"],
    "navigator": ["navigator.", "userAgent", "platform", "language",
                  "hardwareConcurrency", "deviceMemory", "vendor"],
    "screen":    ["screen.", "colorDepth", "pixelDepth", "availWidth",
                  "availHeight", "Screen"],
    "crypto":    ["crypto.", "getRandomValues", "SubtleCrypto", "subtle"],
    "storage":   ["localStorage", "sessionStorage", "indexedDB", "cookie", "Cookie"],
    "font":      ["FontFace", "measureText", "font", "Font"],
    "time":      ["performance.", "Date.now", "Performance", "performance.now"],
    "webgpu":    ["GPU", "GPUAdapter", "GPUDevice", "navigator.gpu"],
}


def event_api(event):
    """Return a stable API name for legacy and current DOMTrace schemas."""
    if not isinstance(event, dict):
        return ""
    api = event.get("api")
    if isinstance(api, str) and api:
        return api
    interface = event.get("interface")
    member = event.get("member")
    parts = [part for part in (interface, member) if isinstance(part, str) and part]
    return ".".join(parts)


def format_stack(stack):
    if isinstance(stack, str):
        return stack
    if not isinstance(stack, list):
        return ""
    rendered = []
    for frame in stack[:3]:
        if isinstance(frame, str):
            rendered.append(frame)
            continue
        if not isinstance(frame, dict):
            continue
        file = frame.get("file", "?")
        line = frame.get("line", "?")
        col = frame.get("col", "?")
        rendered.append(f"{file}:{line}:{col}")
    return " <- ".join(rendered)


def empty_trace_diagnostics():
    return {
        "raw_invalid_lines": 0,
        "repaired_lines": 0,
        "unrecoverable_lines": 0,
        "repair_details": [],
        "unrecoverable_details": [],
    }


def repair_known_domtrace_line(line, error):
    """Return a repaired event for the one evidenced serializer defect.

    Repair is deliberately narrow: the bad boundary must occur exactly once,
    the JSON parser must stop at that boundary, removing only the extra
    backslash must produce valid JSON, and the decoded event must match the
    observed ``typeof`` Function-source structure.  Ambiguous or unrelated
    malformed input is never guessed at.
    """
    positions = []
    start = 0
    while True:
        position = line.find(FUNCTION_SOURCE_BAD_BOUNDARY, start)
        if position < 0:
            break
        positions.append(position)
        start = position + 1
    if len(positions) != 1:
        return None

    position = positions[0]
    result_offset = FUNCTION_SOURCE_BAD_BOUNDARY.index("result")
    if error.msg != "Expecting ',' delimiter" or error.pos != position + result_offset:
        return None

    candidate = line[:position] + line[position + 1 :]
    try:
        event = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    if not isinstance(event, dict):
        return None
    operand = event.get("operand")
    if not (
        event.get("type") == "typeof"
        and event.get("result") == "function"
        and isinstance(operand, dict)
        and operand.get("type") == "Function"
        and isinstance(operand.get("source"), str)
        and isinstance(event.get("stack"), list)
    ):
        return None
    return event, FUNCTION_SOURCE_REPAIR_REASON


def load_trace(path):
    events = []
    diagnostics = empty_trace_diagnostics()
    with open(path, "r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, 1):
            line = raw_line.rstrip("\r\n")
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                diagnostics["raw_invalid_lines"] += 1
                repaired = repair_known_domtrace_line(line, error)
                if repaired is None:
                    diagnostics["unrecoverable_lines"] += 1
                    diagnostics["unrecoverable_details"].append(
                        {
                            "line": line_number,
                            "reason": error.msg,
                            "column": error.colno,
                        }
                    )
                    continue
                event, reason = repaired
                events.append(event)
                diagnostics["repaired_lines"] += 1
                diagnostics["repair_details"].append(
                    {"line": line_number, "reason": reason}
                )
                continue
            if not isinstance(event, dict):
                diagnostics["raw_invalid_lines"] += 1
                diagnostics["unrecoverable_lines"] += 1
                diagnostics["unrecoverable_details"].append(
                    {
                        "line": line_number,
                        "reason": "trace event must be a JSON object",
                        "column": 1,
                    }
                )
                continue
            events.append(event)
    return events, diagnostics


def categorize(events):
    result = defaultdict(list)
    for e in events:
        api = event_api(e)
        if not api:
            continue
        for cat, keywords in CATEGORIES.items():
            if any(kw in api for kw in keywords):
                result[cat].append(e)
                break
    return result


def normalize_trace_diagnostics(diagnostics=None):
    if diagnostics is None:
        return empty_trace_diagnostics()
    if isinstance(diagnostics, int):
        # Backward-compatible input for callers using the former API.
        normalized = empty_trace_diagnostics()
        normalized["raw_invalid_lines"] = diagnostics
        normalized["unrecoverable_lines"] = diagnostics
        return normalized
    normalized = empty_trace_diagnostics()
    for key in ("raw_invalid_lines", "repaired_lines", "unrecoverable_lines"):
        normalized[key] = int(diagnostics.get(key, 0))
    for key in ("repair_details", "unrecoverable_details"):
        normalized[key] = list(diagnostics.get(key, []))
    return normalized


def build_summary(events, categorized, diagnostics=None):
    trace_diagnostics = normalize_trace_diagnostics(diagnostics)
    call_apis = [event_api(event) for event in events]
    call_apis = [api for api in call_apis if api]
    call_events = sum(
        1
        for event in events
        if event_api(event)
        and (event.get("type") == "call" or ("type" not in event and "api" in event))
    )
    return {
        "schema_version": 2,
        "total_events": len(events),
        "api_events": len(call_apis),
        "call_events": call_events,
        # ``invalid_lines`` remains as a compatibility alias for lines that
        # could not be recovered. Raw serializer defects stay separately visible.
        "invalid_lines": trace_diagnostics["unrecoverable_lines"],
        **trace_diagnostics,
        "unique_apis": len(set(call_apis)),
        "categories": {
            category: {
                "calls": len(categorized.get(category, [])),
                "unique_apis": sorted(
                    {event_api(event) for event in categorized.get(category, [])}
                ),
            }
            for category in CATEGORIES
            if categorized.get(category)
        },
    }


def stats(events, categorized, diagnostics=None):
    summary = build_summary(events, categorized, diagnostics)
    print(f"Total events: {len(events)}")
    print(f"API events:   {summary['api_events']}")
    print(f"Call events:  {summary['call_events']}")
    print(f"Unique APIs:  {summary['unique_apis']}")
    if summary["raw_invalid_lines"]:
        print(f"Raw invalid lines:  {summary['raw_invalid_lines']}")
        print(f"Repaired lines:     {summary['repaired_lines']}")
        print(f"Unrecoverable lines: {summary['unrecoverable_lines']}")
    print()
    for cat in CATEGORIES:
        c = categorized.get(cat, [])
        if c:
            apis = sorted({event_api(event) or "?" for event in c})
            print(f"  {cat}: {len(c)} calls, {len(apis)} unique APIs")
    print()


def print_category(categorized, target):
    events = categorized.get(target, [])
    if not events:
        print(f"No '{target}' events found.")
        return
    apis = defaultdict(list)
    for e in events:
        apis[event_api(e) or "?"].append(e)
    print(f"=== {target} ({len(events)} calls, {len(apis)} unique) ===")
    for api, calls in sorted(apis.items()):
        print(f"\n  {api} ({len(calls)} calls):")
        for c in calls[:3]:
            args = c.get("args", [])
            stack = format_stack(c.get("stack", ""))
            if args:
                print(f"    args: {json.dumps(args, ensure_ascii=False)[:200]}")
            if stack:
                print(f"    stack: {stack[:120]}")


def main():
    parser = argparse.ArgumentParser(description="ruyiTrace NDJSON analyzer")
    parser.add_argument("trace", help="Path to trace .ndjson file")
    parser.add_argument("--category", "-c", default="all",
                       choices=["all"] + list(CATEGORIES.keys()),
                       help="Filter by category")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable summary")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 2 when any NDJSON line remains unrecoverable",
    )
    args = parser.parse_args()

    events, diagnostics = load_trace(args.trace)
    categorized = categorize(events)
    summary = build_summary(events, categorized, diagnostics)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        stats(events, categorized, diagnostics)

        if args.category != "all":
            print_category(categorized, args.category)
        else:
            for cat in CATEGORIES:
                if categorized.get(cat):
                    print(f"  {cat}: {len(categorized[cat])} calls")

    if args.strict and summary["unrecoverable_lines"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
