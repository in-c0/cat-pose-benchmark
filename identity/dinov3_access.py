from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, NamedTuple

PIN_PATH = Path(__file__).with_name("dinov3_backbone_pin.json")

HF_ENDPOINT = "https://huggingface.co"
TOKEN_ENV_VARS = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN")

STATUS_OK = "ok"
STATUS_TOKEN_MISSING = "token_missing"
STATUS_TOKEN_INVALID = "token_invalid"
STATUS_GATE_NOT_ACCEPTED = "gate_not_accepted"
STATUS_MODEL_NOT_FOUND = "model_not_found"
STATUS_NETWORK_UNREACHABLE = "network_unreachable"
STATUS_UNEXPECTED = "unexpected_response"

REMEDIES = {
    STATUS_TOKEN_MISSING: (
        "No Hugging Face token in the environment. In GitHub: Settings -> Secrets and "
        "variables -> Actions -> New repository secret, name HF_TOKEN. Note that secrets "
        "are not exposed to workflow runs triggered from forked pull requests."
    ),
    STATUS_TOKEN_INVALID: (
        "Hugging Face rejected the token. Regenerate a read token at "
        "https://huggingface.co/settings/tokens and update the HF_TOKEN secret. A revoked, "
        "truncated, or whitespace-padded value produces this."
    ),
    STATUS_GATE_NOT_ACCEPTED: (
        "The token is valid but the account has not been granted access to this gated "
        "repository. Open the model page while logged in as that same account, accept the "
        "access conditions, and wait for the request to show as granted. If the token is "
        "fine-grained, it also needs the scope 'Read access to contents of all public gated "
        "repos you can access'."
    ),
    STATUS_MODEL_NOT_FOUND: (
        "Hugging Face does not resolve this repo id for this account. Correct 'repo_id' in "
        "identity/dinov3_backbone_pin.json to the exact id shown on the model page."
    ),
    STATUS_NETWORK_UNREACHABLE: (
        "huggingface.co could not be reached. In a sandboxed or proxied environment this is "
        "usually the network policy denying the host rather than a credential problem."
    ),
    STATUS_UNEXPECTED: (
        "Unexpected response from Hugging Face. Treat the backbone as unavailable rather than "
        "assuming access."
    ),
}


class DINOv3AccessError(RuntimeError):
    pass


class HttpResponse(NamedTuple):
    status: int
    body: str


Transport = Callable[[str, str, "str | None"], HttpResponse]


def load_pin(path: Path = PIN_PATH) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("pin_version") != "DINOV3-S-PIN-v0":
        raise DINOv3AccessError("expected a DINOV3-S-PIN-v0 backbone pin")
    if not str(raw.get("repo_id", "")).strip():
        raise DINOv3AccessError("backbone pin is missing repo_id")
    if raw.get("revision_verified"):
        revision = str(raw.get("revision") or "")
        if len(revision) != 40 or any(ch not in "0123456789abcdef" for ch in revision.lower()):
            raise DINOv3AccessError(
                "revision_verified pin must carry a 40-character commit SHA, not a branch name"
            )
    return raw


def resolve_token(env: "dict[str, str] | None" = None) -> "str | None":
    """Return the first non-empty Hugging Face token in the environment, or None.

    The value is never logged; only its presence is ever reported.
    """
    source = os.environ if env is None else env
    for name in TOKEN_ENV_VARS:
        value = str(source.get(name, "") or "").strip()
        if value:
            return value
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Stop at the redirect instead of replaying the bearer token to the CDN host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def _urllib_transport(method: str, url: str, token: "str | None") -> HttpResponse:
    request = urllib.request.Request(url, method=method)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=30) as response:
            return HttpResponse(response.status, response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return HttpResponse(exc.code, exc.read().decode("utf-8", "replace"))
    except urllib.error.URLError as exc:
        raise DINOv3AccessError(f"network failure reaching {HF_ENDPOINT}: {exc.reason}") from exc
    except OSError as exc:  # proxy CONNECT refusal surfaces here
        raise DINOv3AccessError(f"network failure reaching {HF_ENDPOINT}: {exc}") from exc


def _result(status: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": status, "ok": status == STATUS_OK}
    payload.update(extra)
    if status != STATUS_OK:
        payload["remedy"] = REMEDIES[status]
    return payload


def check_access(
    *,
    pin: "dict[str, Any] | None" = None,
    token: "str | None" = None,
    transport: "Transport | None" = None,
) -> dict[str, Any]:
    """Probe whether this environment can actually download the pinned DINOv3 backbone.

    Three probes, so that a failure names its own cause instead of collapsing every
    problem into one opaque 401:

      1. whoami   -- is the token itself valid?
      2. model    -- does the repo id resolve, and is it gated?
      3. resolve  -- is this account actually entitled to the weights?
    """
    pin = load_pin() if pin is None else pin
    send = _urllib_transport if transport is None else transport
    repo_id = str(pin["repo_id"])
    revision = str(pin.get("revision") or "main")
    probe_file = str(pin.get("entitlement_probe_file") or "config.json")
    context = {"repo_id": repo_id, "revision": revision}

    if token is None:
        return _result(STATUS_TOKEN_MISSING, **context)

    try:
        whoami = send("GET", f"{HF_ENDPOINT}/api/whoami-v2", token)
        if whoami.status in (401, 403):
            return _result(STATUS_TOKEN_INVALID, **context)
        if whoami.status != 200:
            return _result(STATUS_UNEXPECTED, http_status=whoami.status, probe="whoami", **context)

        account = None
        try:
            account = json.loads(whoami.body).get("name")
        except (ValueError, AttributeError):
            pass
        context["account"] = account

        info = send("GET", f"{HF_ENDPOINT}/api/models/{repo_id}", token)
        if info.status == 404:
            return _result(STATUS_MODEL_NOT_FOUND, **context)
        if info.status == 200:
            try:
                context["resolved_sha"] = json.loads(info.body).get("sha")
            except (ValueError, AttributeError):
                pass
            head = context.get("resolved_sha")
            pinned = str(pin.get("revision") or "")
            if pin.get("revision_verified") and head and head != pinned:
                # Not a failure: the pinned revision is what makes the run reproducible.
                context["upstream_head_moved"] = True
        elif info.status != 403:
            return _result(STATUS_UNEXPECTED, http_status=info.status, probe="model_info", **context)

        entitlement = send(
            "HEAD", f"{HF_ENDPOINT}/{repo_id}/resolve/{revision}/{probe_file}", token
        )
    except DINOv3AccessError as exc:
        return _result(STATUS_NETWORK_UNREACHABLE, detail=str(exc), **context)

    if entitlement.status in (200, 302):
        return _result(STATUS_OK, **context)
    if entitlement.status == 403:
        return _result(STATUS_GATE_NOT_ACCEPTED, **context)
    if entitlement.status == 401:
        # whoami already accepted the token, so a 401 here is the gate, not the credential.
        return _result(STATUS_GATE_NOT_ACCEPTED, **context)
    if entitlement.status == 404:
        return _result(STATUS_MODEL_NOT_FOUND, **context)
    return _result(
        STATUS_UNEXPECTED, http_status=entitlement.status, probe="entitlement", **context
    )


def followup_note(report: dict[str, Any], pin: dict[str, Any]) -> "str | None":
    """Return the operator note for a successful preflight, or None if nothing to say."""
    sha = report.get("resolved_sha")
    if not sha:
        return None
    if not pin.get("revision_verified"):
        return (
            f'Backbone reachable. To freeze it, set "revision": "{sha}" and '
            '"revision_verified": true in identity/dinov3_backbone_pin.json.'
        )
    if report.get("upstream_head_moved"):
        return (
            f"Backbone reachable at the pinned revision. Note that the upstream branch head "
            f"has since moved to {sha}; the pin is deliberately unchanged, so ID1 results "
            "remain comparable. Re-pinning is an explicit re-baselining decision."
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight the gated DINOv3 backbone pinned for the ID1.0 REMIND baseline. "
            "Never prints the token."
        )
    )
    parser.add_argument("--pin", type=Path, default=PIN_PATH)
    parser.add_argument("--output", type=Path, help="write the JSON report here")
    parser.add_argument(
        "--allow-missing-token",
        action="store_true",
        help="exit 0 when no token is present (for runs without access to repository secrets)",
    )
    args = parser.parse_args()

    pin = load_pin(args.pin)
    report = check_access(pin=pin, token=resolve_token())
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")

    if report["ok"]:
        note = followup_note(report, pin)
        if note:
            print("\n" + note)
        return 0
    if report["status"] == STATUS_TOKEN_MISSING and args.allow_missing_token:
        print("\nNo token available; treating the backbone as not-yet-configured.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
