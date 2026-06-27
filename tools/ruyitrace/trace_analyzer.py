"""Parse ruyiTrace NDJSON output, extract fingerprint API calls by category.

Usage:
    python trace_analyzer.py <trace.ndjson> [--category canvas|webgl|audio|all]
"""

import json, sys, argparse
from collections import defaultdict

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

def load_trace(path):
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events

def categorize(events):
    result = defaultdict(list)
    for e in events:
        api = e.get("api", "")
        for cat, keywords in CATEGORIES.items():
            if any(kw in api for kw in keywords):
                result[cat].append(e)
                break
    return result

def stats(events, categorized):
    print(f"Total events: {len(events)}")
    print(f"Unique APIs:  {len(set(e.get('api','?') for e in events))}")
    print()
    for cat in CATEGORIES:
        c = categorized.get(cat, [])
        if c:
            apis = sorted(set(e.get("api", "?") for e in c))
            print(f"  {cat}: {len(c)} calls, {len(apis)} unique APIs")
    print()

def print_category(categorized, target):
    events = categorized.get(target, [])
    if not events:
        print(f"No '{target}' events found.")
        return
    apis = defaultdict(list)
    for e in events:
        apis[e.get("api", "?")].append(e)
    print(f"=== {target} ({len(events)} calls, {len(apis)} unique) ===")
    for api, calls in sorted(apis.items()):
        print(f"\n  {api} ({len(calls)} calls):")
        for c in calls[:3]:
            args = c.get("args", [])
            stack = c.get("stack", "")
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
    args = parser.parse_args()

    events = load_trace(args.trace)
    categorized = categorize(events)
    stats(events, categorized)

    if args.category != "all":
        print_category(categorized, args.category)
    else:
        for cat in CATEGORIES:
            if categorized.get(cat):
                print(f"  {cat}: {len(categorized[cat])} calls")

if __name__ == "__main__":
    main()
