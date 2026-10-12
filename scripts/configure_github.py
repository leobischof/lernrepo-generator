"""Idempotent GitHub policy setup, explicitly authorized with --apply."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/conventions.py"
spec = importlib.util.spec_from_file_location("conventions", SCRIPT)
conventions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(conventions)


def policy():
    return {
        "settings": dict(default_branch="main", allow_squash_merge=True, allow_merge_commit=False,
                         allow_rebase_merge=False, delete_branch_on_merge=True, allow_auto_merge=False,
                         squash_merge_commit_title="PR_TITLE", squash_merge_commit_message="PR_BODY"),
        "protection": dict(required_status_checks=dict(strict=True, contexts=["qa", "konventionen"]),
                           enforce_admins=True, required_pull_request_reviews=dict(
                               dismiss_stale_reviews=True, require_code_owner_reviews=False,
                               required_approving_review_count=0, require_last_push_approval=False),
                           restrictions=None, required_linear_history=True, allow_force_pushes=False,
                           allow_deletions=False, required_conversation_resolution=True),
        "rulesets": [conventions.ruleset(),
                     dict(name="alle Branches: kein Force-Push", target="branch", enforcement="active",
                          bypass_actors=[], conditions=dict(ref_name=dict(include=["~ALL"], exclude=[])),
                          rules=[dict(type="non_fast_forward")]),
                     dict(name="main: nur per PR, linear, nicht löschbar", target="branch", enforcement="active",
                          bypass_actors=[], conditions=dict(ref_name=dict(include=["~DEFAULT_BRANCH"], exclude=[])),
                          rules=[dict(type="deletion"), dict(type="non_fast_forward"), dict(type="required_linear_history"),
                                 dict(type="pull_request", parameters=dict(required_approving_review_count=0,
                                      dismiss_stale_reviews_on_push=True, required_reviewers=[],
                                      require_code_owner_review=False, require_last_push_approval=False,
                                      required_review_thread_resolution=True,
                                      require_extra_approval_for_unattributed_changes=True,
                                      allowed_merge_methods=["merge", "squash", "rebase"]))])]
    }


def api(endpoint, method="GET", body=None):
    args = ["gh", "api", endpoint, "--method", method]
    if body is not None:
        args += ["--input", "-"]
    result = subprocess.run(args, input=json.dumps(body) if body is not None else None,
                            check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(result.stdout) if result.stdout.strip() else None


def apply(repo):
    prefix = "repos/" + repo
    api(prefix + "/branches/main")  # Fail before mutation if bootstrap is missing.
    config = policy()
    api(prefix, "PATCH", config["settings"])
    api(prefix + "/branches/main/protection", "PUT", config["protection"])
    existing = {r["name"]: r["id"] for r in api(prefix + "/rulesets?per_page=100")}
    for rule in config["rulesets"]:
        suffix = "/" + str(existing[rule["name"]]) if rule["name"] in existing else ""
        api(prefix + "/rulesets" + suffix, "PUT" if suffix else "POST", rule)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        parser.error("--repo muss OWNER/REPO sein")
    if args.apply:
        apply(args.repo)
        print("GitHub-Policy eingerichtet: " + args.repo)
    else:
        print(json.dumps(policy(), ensure_ascii=False, indent=2))
