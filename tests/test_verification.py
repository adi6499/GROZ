"""Verification by a person: the ledger, its effect on the website, and the local review server."""

import copy
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone

import pytest

from backend.review import verification as v
from backend.site import catalogue_export as cx

WHEN = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def records():
    with open(cx.DATASET, encoding="utf-8") as f:
        return json.load(f)


def rec(records, cat):
    return next(r for r in records if r["cat_nr"] == cat)


# ---------------------------------------------------------------- ledger rules

def test_fingerprint_covers_the_checked_values_only(records):
    r = rec(records, "G/10/M1")
    fp = v.fingerprint(r)
    assert fp == v.fingerprint(copy.deepcopy(r))
    for change in (lambda x: x.update(ord_nr="07799"), lambda x: x.update(sub_title="Other"),
                   lambda x: x["specifications"].update(table_caption="X"), lambda x: x.update(box_qty=1),
                   lambda x: x["images"].clear()):
        other = copy.deepcopy(r)
        change(other)
        assert v.fingerprint(other) != fp
    other = copy.deepcopy(r)
    other["confidence"], other["editorial_notes"], other["verification_status"] = 0.1, [{"x": 1}], "needs_review"
    assert v.fingerprint(other) == fp  # scores, notes and status are not values on the page


def test_decisions_need_a_name_a_comment_for_flags_and_current_values(records):
    r, led = rec(records, "G/10/M1"), v.empty_ledger()
    fp = v.fingerprint(r)
    with pytest.raises(v.DecisionError, match="name"):
        v.record_decision(led, "k", r, "verified", "  ", fp)
    with pytest.raises(v.DecisionError, match="comment"):
        v.record_decision(led, "k", r, "flagged", "Asha", fp, comment=" ")
    with pytest.raises(v.DecisionError):
        v.record_decision(led, "k", r, "approved", "Asha", fp)
    with pytest.raises(v.DecisionError, match="changed since"):
        v.record_decision(led, "k", r, "verified", "Asha", "0" * 16)
    assert led["decisions"] == {}
    e = v.record_decision(led, "k", r, "verified", " Asha  K ", fp, now=WHEN)
    assert (e["status"], e["reviewer"], e["at"], e["fingerprint"]) == ("verified", "Asha K", "2026-10-14T09:00:00+00:00", fp)


def test_state_follows_the_values(records):
    r, led = rec(records, "G/10/M1"), v.empty_ledger()
    assert v.state_for(led, "k", r) == (None, None)
    v.record_decision(led, "k", r, "verified", "Asha", v.fingerprint(r))
    assert v.state_for(led, "k", r)[0] == "verified"
    changed = copy.deepcopy(r)
    changed["box_qty"] = 999
    assert v.state_for(led, "k", changed)[0] == "stale"  # a later extraction changed a checked value
    assert v.undo_decision(led, "k")["status"] == "verified" and v.state_for(led, "k", r) == (None, None)


def test_ledger_round_trip_and_append_only_log(tmp_path, records):
    r, led = rec(records, "G/10/M1"), v.empty_ledger()
    v.record_decision(led, "k", r, "flagged", "Asha", v.fingerprint(r), comment="Box qty is 100", fields=["Box quantity"])
    v.save_ledger(led, str(tmp_path / "l.json"))
    assert v.load_ledger(str(tmp_path / "l.json")) == led
    for i in range(2):
        v.append_log({"n": i}, str(tmp_path / "log.jsonl"))
    assert [json.loads(x) for x in open(tmp_path / "log.jsonl", encoding="utf-8")] == [{"n": 0}, {"n": 1}]
    assert v.load_ledger(str(tmp_path / "missing.json")) == v.empty_ledger()


def test_website_shows_only_current_human_decisions(tmp_path, records):
    a, b, c = rec(records, "G/10/M1"), rec(records, "LED/621"), rec(records, "ECH-212X")
    led = v.empty_ledger()
    v.record_decision(led, cx.record_id(a), a, "verified", "Asha", v.fingerprint(a), now=WHEN)
    v.record_decision(led, cx.record_id(b), b, "flagged", "Asha", v.fingerprint(b), comment="Beam angle reads 60 on p12", fields=["Beam angle"], now=WHEN)
    v.record_decision(led, cx.record_id(c), c, "verified", "Asha", v.fingerprint(c), now=WHEN)
    led["decisions"][cx.record_id(c)]["fingerprint"] = "stale0000000000"  # values changed since
    path = str(tmp_path / "ledger.json")
    v.save_ledger(led, path)
    data = cx.build(ledger_path=path)
    by_cat = {p["cat_nr"]: p for p in data["products"]}
    assert (by_cat["G/10/M1"]["status"], by_cat["G/10/M1"]["status_label"]) == ("verified", "Verified")
    assert by_cat["G/10/M1"]["verification"] == {"state": "verified", "reviewer": "Asha", "at": "2026-10-14T09:00:00+00:00"}
    assert by_cat["LED/621"]["status"] == "needs_review"
    assert by_cat["LED/621"]["notes"][-1]["issue"] == "Flagged by Asha on 2026-10-14: Beam angle reads 60 on p12"
    assert by_cat["ECH-212X"]["status"] == c["verification_status"] and by_cat["ECH-212X"]["verification"] is None
    assert (data["meta"]["verified"], data["meta"]["flagged_by_reviewer"], data["meta"]["verification_stale"]) == (1, 1, 1)
    assert sum(1 for p in data["products"] if p["status"] == "verified") == 1  # nothing else becomes verified


# ---------------------------------------------------------------- the review server

@pytest.fixture(scope="module")
def server(tmp_path_factory):
    import verify_server
    tmp = tmp_path_factory.mktemp("review")
    store = verify_server.ReviewStore(cx.DATASET, str(tmp / "ledger.json"), str(tmp / "log.jsonl"), can_publish=False)
    httpd = verify_server.make_server(0, store)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp
    httpd.shutdown()
    httpd.server_close()


def call(base, path, body=None, headers=None):
    h = {"Content-Type": "application/json", "X-GROZ-Review": "1"} if headers is None else headers
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=h,
                                 method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.status, res.read(), res.headers.get("Content-Type")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type")


def test_server_lists_every_product_with_its_fingerprint(server):
    base, _ = server
    code, body, _ = call(base, "/api/review/records")
    data = json.loads(body)
    assert code == 200 and data["total"] == 941 and data["can_publish"] is False
    assert data["counts"] == {"verified": 0, "flagged": 0, "stale": 0, "to_check": 941}
    g = next(r for r in data["records"] if r["cat_nr"] == "G/10/M1")
    assert {x["label"]: x["value"] for x in g["values"]}["Table caption (printed)"] == "TAPER SHANK ARBORS - DIN 238"


def test_server_renders_the_row_and_finds_it(server):
    base, _ = server
    _, body, _ = call(base, "/api/review/records")
    rid = next(r["id"] for r in json.loads(body)["records"] if r["cat_nr"] == "G/10/M1")
    code, body, _ = call(base, f"/api/review/geometry?id={rid}&view=row")
    g = json.loads(body)
    assert code == 200 and g["row_found"] and {b["kind"] for b in g["boxes"]} == {"row", "cat", "ord"}
    code, png, ctype = call(base, f"/api/review/page.png?id={rid}&view=row")
    assert code == 200 and ctype == "image/png" and png[:8] == b"\x89PNG\r\n\x1a\n"
    assert call(base, "/api/review/page.png?id=nope&view=row")[0] == 400
    assert call(base, f"/api/review/page.png?id={rid}&view=../../x")[0] == 400


def test_server_refuses_changes_from_elsewhere_and_stale_values(server):
    base, tmp = server
    _, body, _ = call(base, "/api/review/records")
    r = next(x for x in json.loads(body)["records"] if x["cat_nr"] == "ECH-212X")
    ok = {"id": r["id"], "fingerprint": r["fingerprint"], "status": "verified", "reviewer": "Test"}
    assert call(base, "/api/review/decision", ok, headers={"Content-Type": "application/json"})[0] == 403  # no header
    assert call(base, "/api/review/decision", ok, headers={"Content-Type": "application/json", "X-GROZ-Review": "1",
                                                          "Origin": "https://example.com"})[0] == 403
    assert call(base, "/api/review/decision", {**ok, "fingerprint": "0" * 16})[0] == 409
    assert call(base, "/api/review/decision", {**ok, "reviewer": ""})[0] == 400
    assert call(base, "/api/review/publish", {})[0] == 400  # a test ledger is never published
    assert not os.path.exists(tmp / "ledger.json")


def test_server_records_and_undoes_a_decision(server):
    base, tmp = server
    _, body, _ = call(base, "/api/review/records")
    r = next(x for x in json.loads(body)["records"] if x["cat_nr"] == "ECH-212X")
    code, body, _ = call(base, "/api/review/decision", {"id": r["id"], "fingerprint": r["fingerprint"], "status": "verified", "reviewer": "Test"})
    assert code == 200 and json.loads(body)["record"]["decision"]["state"] == "verified"
    assert v.load_ledger(str(tmp / "ledger.json"))["decisions"][r["id"]]["reviewer"] == "Test"
    code, body, _ = call(base, "/api/review/undo", {"id": r["id"], "reviewer": "Test"})
    assert code == 200 and json.loads(body)["record"]["decision"] is None
    assert v.load_ledger(str(tmp / "ledger.json"))["decisions"] == {}
    actions = [json.loads(x)["action"] for x in open(tmp / "log.jsonl", encoding="utf-8")]
    assert actions == ["verified", "undo"]
