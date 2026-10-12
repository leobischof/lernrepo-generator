import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "scripts/configure_github.py"
SPEC = importlib.util.spec_from_file_location("github_policy", PATH)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_policy_matches_protected_pr_workflow():
    policy = module.policy()
    assert policy["settings"]["allow_squash_merge"]
    assert not policy["settings"]["allow_merge_commit"]
    assert not policy["settings"]["allow_rebase_merge"]
    assert policy["settings"]["delete_branch_on_merge"]
    protection = policy["protection"]
    assert protection["enforce_admins"]
    assert protection["required_status_checks"] == {"strict": True, "contexts": ["qa", "konventionen"]}
    assert protection["required_pull_request_reviews"]["required_approving_review_count"] == 0
    assert protection["required_conversation_resolution"]
    assert not protection["allow_force_pushes"] and not protection["allow_deletions"]
    assert all(r["bypass_actors"] == [] and r["enforcement"] == "active" for r in policy["rulesets"])


def test_setup_is_idempotent_and_checks_main_before_writes(monkeypatch):
    calls = []

    def api(endpoint, method="GET", body=None):
        calls.append((endpoint, method, body))
        if endpoint.endswith("rulesets?per_page=100"):
            return [{"name": r["name"], "id": i} for i, r in enumerate(module.policy()["rulesets"], 1)]
        return {}

    monkeypatch.setattr(module, "api", api)
    module.apply("owner/repo")
    assert calls[0][:2] == ("repos/owner/repo/branches/main", "GET")
    assert [method for _, method, _ in calls] == ["GET", "PATCH", "PUT", "GET", "PUT", "PUT", "PUT"]
