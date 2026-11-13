"""Run deterministic evaluations over the real stdio MCP surface.

Development only; it needs the MCP client SDK and the MCP Eval executable and is not part of the
installed package. No Adobe application is needed. ``protocol`` checks the MCP contract of the
catalog. ``core`` also plays ``cases.json``: every input check that happens before Premiere Pro is
touched, plus the tools that read only the local machine.
"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
SERVER = ["-m", "cavi_premiere_mcp.server"]
# Changes the user's Adobe Bridge installation, so no case plays it.
NOT_PLAYED = {"premiere_bridge_install"}
# What a case may fail with; anything else is a defect in the runner and propagates.
CASE_ERRORS = (AssertionError, KeyError, TypeError, ValueError, OSError)


def pointer(value, path):
    """The part of ``value`` that a JSON pointer such as ``/export`` names."""
    for key in path.strip("/").split("/"):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def load_corpus():
    corpus = json.loads((ROOT / "evals/cases.json").read_text())
    if len({case["id"] for case in corpus}) != len(corpus):
        raise ValueError("Corpus case IDs must be unique")
    return corpus


async def exercise(env):
    corpus = load_corpus()
    results = []
    params = StdioServerParameters(command=sys.executable, args=SERVER, env=env)
    async with (
        stdio_client(params) as (reader, writer),
        ClientSession(reader, writer, read_timeout_seconds=90.0) as session,
    ):
        await session.initialize()
        tools = {tool.name for tool in (await session.list_tools()).tools}
        covered = {case["tool"] for case in corpus}
        if tools - covered != NOT_PLAYED or covered - tools:
            raise AssertionError(f"Tool coverage drift: uncovered={tools - covered - NOT_PLAYED}, "
                                 f"unknown={covered - tools}")
        for case in corpus:
            try:
                reply = await session.call_tool(case["tool"], case["arguments"])
                text = "\n".join(getattr(item, "text", "") for item in reply.content)
                if case.get("error"):
                    assert reply.is_error, "Expected an explicit MCP tool error"
                    assert case["error"].lower() in text.lower(), text
                else:
                    assert not reply.is_error, text
                    for path in case.get("required", []):
                        pointer(reply.structured_content, path)
                results.append({"id": case["id"], "tool": case["tool"], "kind": case["kind"], "passed": True})
            except CASE_ERRORS as exc:
                results.append({"id": case["id"], "tool": case["tool"], "kind": case["kind"], "passed": False,
                                "reason": str(exc)})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["protocol", "core"])
    args = parser.parse_args()
    evaluator = Path(os.environ.get(
        "MCPEVAL_EXECUTABLE", ROOT / "node_modules/.bin/mcpeval")).expanduser().resolve()
    if not evaluator.is_file() or not os.access(evaluator, os.X_OK):
        parser.error("Install the evaluator with npm install or set MCPEVAL_EXECUTABLE")
    output_root = ROOT / ".tmp/evals"
    output_root.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix=f"{args.mode}-", dir=output_root))
    # The server reads and writes under HOME (the Bridge relay mailbox); give it an empty one.
    home = output / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "MCPEVAL_HOME": str(output / "store")}
    results = asyncio.run(exercise(env)) if args.mode == "core" else []
    (output / "cases.json").write_text(json.dumps(
        {"mode": args.mode, "application": "premiere", "cases": results,
         "native_evidence": False, "native_status": "not run: no Adobe application is used",
         "model_evaluation": "not supported"}, indent=2) + "\n")
    version = subprocess.run([str(evaluator), "--version"], capture_output=True, text=True, check=True,
                             timeout=30).stdout.strip()
    (output / "evaluator.json").write_text(json.dumps({
        "version": version,
        "sha256": hashlib.sha256(evaluator.read_bytes()).hexdigest(),
        "source": "MCPEVAL_EXECUTABLE" if "MCPEVAL_EXECUTABLE" in os.environ else "npm",
        "source_revision": os.environ.get("MCPEVAL_SOURCE_REVISION"),
        "npm_dependency": "github:cavi-ai/mcp-eval#main",
    }, indent=2) + "\n")
    command = [str(evaluator), "probe", "--server", f"premiere-{args.mode}", "--manifest",
               str(ROOT / f"evals/{args.mode}.manifest.json"), "--format", "json",
               # Only the manifest gate: the readiness score needs tools that run Premiere Pro.
               "--gate-only", "--", sys.executable, *SERVER]
    with (output / "mcpeval.json").open("w") as stream:
        evaluated = subprocess.run(command, env=env, cwd=ROOT, stdout=stream, check=False)
    failed = [case for case in results if not case["passed"]]
    print(json.dumps({"mode": args.mode, "passed": len(results) - len(failed), "failed": failed,
                      "mcpeval_exit": evaluated.returncode, "artifacts": str(output)}, indent=2))
    if failed or evaluated.returncode:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
