from datetime import datetime, timezone
import json


def append(path, *, stage, model, inputs, result, usage=None):
    entry = dict(time=datetime.now(timezone.utc).isoformat(), stage=stage, model=model,
                 inputs=inputs, result=result, usage=usage)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
