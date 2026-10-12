"""Explicit-start Chat Completions adapter; no hidden calls, keys or retries."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from .ailog import append
from .contracts import SYSTEM
from .io import read, write
from .jobs import make_jobs, plan, validate_result


def run(course, *, start=False, max_jobs=1, transport=None):
    summary = plan(course)
    if not start:
        return summary
    if max_jobs < 1:
        raise ValueError("max-jobs muss positiv sein")
    config = course.data["llm"]
    parsed = urllib.parse.urlparse(config["base_url"])
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("API base_url fehlt/ungültig; Zugangsdaten nur in Umgebungsvariablen")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Entfernte API-Endpunkte benötigen HTTPS")
    if not config["model"]:
        raise ValueError("Modell in course.yaml eintragen")
    key = os.environ.get(config["api_key_env"], "")
    if not key and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError(f"API-Schlüssel fehlt: Umgebungsvariable {config['api_key_env']}")
    token_field = config.get("token_limit_field", "max_completion_tokens")
    if token_field not in {"max_completion_tokens", "max_tokens"}:
        raise ValueError("token_limit_field: max_completion_tokens oder max_tokens")
    done = 0
    for job in make_jobs(course):
        dest = course.path("results") / f"{job['job_id']}.json"
        cached = read(dest, {})
        if cached.get("input_hash") == job["input_hash"]:
            validate_result(job, cached)
            continue
        if done >= max_jobs:
            break
        payload = {"model": config["model"], token_field: config["max_output_tokens"],
                   "messages": [{"role": "system", "content": SYSTEM},
                                {"role": "user", "content": json.dumps(job, ensure_ascii=False)}]}
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = "Bearer " + key
        request = urllib.request.Request(config["base_url"].rstrip("/") + "/chat/completions",
                                         json.dumps(payload).encode(), headers)
        try:
            if transport:
                response = transport(request)
            else:
                with urllib.request.urlopen(request, timeout=180) as stream:
                    response = json.load(stream)
            choice = response["choices"][0]
            if choice.get("finish_reason") not in {None, "stop"}:
                raise ValueError("Modellausgabe unvollständig; Auftrag kleiner teilen oder Ausgabelimit erhöhen")
            text = choice["message"]["content"]
            if text.startswith("```json") and text.rstrip().endswith("```"):
                text = text.strip()[7:-3].strip()
            result = json.loads(text)
            write(course.path("responses") / dest.name, result)
            validate_result(job, result)
            write(dest, result)
            append(course.path("log"), stage="api", model=config["model"], inputs=[job["input_hash"]],
                   result=dest.name, usage=response.get("usage"))
            done += 1
            print(f"API-Auftrag fertig: {job['job_id']}", flush=True)
        except urllib.error.HTTPError as exc:
            append(course.path("log"), stage="api-error", model=config["model"],
                   inputs=[job["input_hash"]], result=f"HTTP {exc.code}")
            raise ValueError(f"API-Fehler HTTP {exc.code}; kein automatischer Wiederholungsaufruf") from None
        except Exception as exc:
            append(course.path("log"), stage="api-error", model=config["model"],
                   inputs=[job["input_hash"]], result=type(exc).__name__)
            raise
    return {"completed": done, "plan": summary}
