#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable
import urllib.error
import urllib.request
import uuid


DEFAULT_BASE_URL = "http://localhost:8080"
DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ops-derived-sample.json"
)
DEFAULT_ADMIN_EMAIL = "seed-admin@example.com"
DEFAULT_ADMIN_PASSWORD = "imjing12!"


@dataclass(frozen=True)
class FetchResult:
    status_code: int
    body_text: str | None = None


@dataclass(frozen=True)
class ListCheck:
    name: str
    path: str
    minimum_count: int


@dataclass(frozen=True)
class ListCheckResult:
    name: str
    url: str
    status_code: int
    item_count: int
    minimum_count: int


@dataclass(frozen=True)
class DetailCheck:
    name: str
    path: str
    expected_snippet: str


@dataclass(frozen=True)
class DetailCheckResult:
    name: str
    url: str
    status_code: int
    expected_snippet: str


@dataclass(frozen=True)
class ReadModelCheckResult:
    name: str
    url: str
    status_code: int
    expectation: str


@dataclass(frozen=True)
class AuthCheckResult:
    name: str
    url: str
    status_code: int
    expectation: str


@dataclass(frozen=True)
class WriteCheckResult:
    name: str
    url: str
    status_code: int
    expectation: str


PUBLISHED_ANNOUNCEMENT_ID = "92000000-0000-0000-0000-000000000001"
OPEN_SUPPORT_TICKET_ID = "93000000-0000-0000-0000-000000000001"
UNREAD_NOTIFICATION_ID = "94000000-0000-0000-0000-000000000101"


class RuntimeVerificationError(RuntimeError):
    pass


Fetch = Callable[[str, str], FetchResult]
AuthenticatedFetch = Callable[[str, str], FetchResult]


def build_fetch(timeout: float = 10.0):
    def fetch(
        url: str,
        method: str,
        *,
        headers: dict[str, str] | None = None,
        body_bytes: bytes | None = None,
    ) -> FetchResult:
        request = urllib.request.Request(
            url,
            method=method,
            headers=headers or {},
            data=body_bytes,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return FetchResult(
                    status_code=response.getcode(),
                    body_text=response.read().decode("utf-8", errors="replace"),
                )
        except urllib.error.HTTPError as exc:
            return FetchResult(
                status_code=exc.code,
                body_text=exc.read().decode("utf-8", errors="replace"),
            )

    return fetch


def load_fixture(fixture_path: Path) -> dict[str, object]:
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def build_list_checks(fixture_path: Path) -> tuple[ListCheck, ...]:
    fixture = load_fixture(fixture_path)
    return (
        ListCheck("companies", "/api/org/companies/", len(fixture["organizations"])),
        ListCheck("drivers", "/api/drivers/", len(fixture["drivers"])),
        ListCheck("vehicles", "/api/vehicles/vehicle-masters/", len(fixture["vehicles"])),
        ListCheck("announcements", "/api/announcements/", 2),
        ListCheck("support_tickets", "/api/ticket/tickets/", 2),
        ListCheck("general_notifications", "/api/notifications/general/", 2),
        ListCheck("regions", "/api/regions/", len(fixture.get("regions", []))),
        ListCheck(
            "region_daily_statistics",
            "/api/region-analytics/daily-statistics/",
            len(fixture.get("region_analytics", {}).get("daily_statistics", [])),
        ),
        ListCheck(
            "region_performance_summaries",
            "/api/region-analytics/performance-summaries/",
            len(fixture.get("region_analytics", {}).get("performance_summaries", [])),
        ),
        ListCheck(
            "personnel_documents",
            "/api/personnel-documents/documents/",
            len(fixture.get("personnel_documents", [])),
        ),
        ListCheck(
            "assignments",
            "/api/driver-vehicle-assignments/assignments/",
            len(fixture["assignments"]),
        ),
        ListCheck("dispatch_plans", "/api/dispatch/plans/", len(fixture["dispatch"]["plans"])),
        ListCheck(
            "delivery_records",
            "/api/delivery-record/records/",
            len(fixture["delivery_records"]["records"]),
        ),
        ListCheck(
            "settlement_runs",
            "/api/settlements/runs/",
            len(fixture["settlements"]["runs"]),
        ),
    )


def build_detail_checks(fixture_path: Path) -> tuple[DetailCheck, ...]:
    fixture = load_fixture(fixture_path)
    first_company = fixture["organizations"][0]
    first_fleet = first_company["fleets"][0]
    first_driver = fixture["drivers"][0]
    first_vehicle = fixture["vehicles"][0]
    first_region = fixture["regions"][0]
    first_document = fixture["personnel_documents"][0]
    first_assignment = fixture["assignments"][0]
    first_dispatch_plan = fixture["dispatch"]["plans"][0]
    first_vehicle_schedule = fixture["dispatch"]["schedules"][0]
    first_dispatch_assignment = fixture["dispatch"]["assignments"][0]
    first_snapshot = fixture["delivery_records"]["snapshots"][0]
    return (
        DetailCheck(
            "company_detail",
            f"/api/org/companies/{first_company['company_id']}/",
            first_company["name"],
        ),
        DetailCheck(
            "fleet_detail",
            f"/api/org/fleets/{first_fleet['fleet_id']}/",
            first_fleet["name"],
        ),
        DetailCheck(
            "driver_detail",
            f"/api/drivers/{first_driver['driver_id']}/",
            first_driver["name"],
        ),
        DetailCheck(
            "vehicle_detail",
            f"/api/vehicles/vehicle-masters/{first_vehicle['vehicle_id']}/",
            first_vehicle["plate_number"],
        ),
        DetailCheck(
            "region_detail",
            f"/api/regions/{first_region['region_id']}/",
            first_region["name"],
        ),
        DetailCheck(
            "personnel_document_detail",
            f"/api/personnel-documents/documents/{first_document['personnel_document_id']}/",
            first_document["title"],
        ),
        DetailCheck(
            "assignment_detail",
            f"/api/driver-vehicle-assignments/assignments/{first_assignment['driver_vehicle_assignment_id']}/",
            first_assignment["driver_vehicle_assignment_id"],
        ),
        DetailCheck(
            "dispatch_plan_detail",
            f"/api/dispatch/plans/{first_dispatch_plan['dispatch_plan_id']}/",
            first_dispatch_plan["dispatch_plan_id"],
        ),
        DetailCheck(
            "vehicle_schedule_detail",
            f"/api/dispatch/vehicle-schedules/{first_vehicle_schedule['vehicle_schedule_id']}/",
            first_vehicle_schedule["vehicle_schedule_id"],
        ),
        DetailCheck(
            "dispatch_assignment_detail",
            f"/api/dispatch/assignments/{first_dispatch_assignment['dispatch_assignment_id']}/",
            first_dispatch_assignment["dispatch_assignment_id"],
        ),
        DetailCheck(
            "daily_snapshot_detail",
            f"/api/delivery-record/daily-snapshots/{first_snapshot['daily_delivery_input_snapshot_id']}/",
            first_snapshot["daily_delivery_input_snapshot_id"],
        ),
    )


def build_seeded_detail_checks() -> tuple[DetailCheck, ...]:
    return (
        DetailCheck(
            "announcement_detail",
            f"/api/announcements/{PUBLISHED_ANNOUNCEMENT_ID}/",
            "Policy Update For Operators",
        ),
        DetailCheck(
            "support_ticket_detail",
            f"/api/ticket/tickets/{OPEN_SUPPORT_TICKET_ID}/",
            "Driver App Inquiry",
        ),
        DetailCheck(
            "general_notification_detail",
            f"/api/notifications/general/{UNREAD_NOTIFICATION_ID}/",
            "Operator Policy Updated",
        ),
    )


def run_list_checks(
    *,
    base_url: str,
    email: str,
    password: str,
    fixture_path: Path,
    fetch,
) -> tuple[ListCheckResult, ...]:
    normalized_base_url = base_url.rstrip("/")
    token = authenticate(
        base_url=normalized_base_url,
        email=email,
        password=password,
        fetch=fetch,
    )

    results: list[ListCheckResult] = []
    for check in build_list_checks(fixture_path):
        url = f"{normalized_base_url}{check.path}"
        response = fetch(
            url,
            "GET",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            raise RuntimeVerificationError(
                f"{check.name}: expected 200, got {response.status_code}"
            )
        count = extract_item_count(response.body_text or "")
        if count < check.minimum_count:
            raise RuntimeVerificationError(
                f"{check.name}: expected at least {check.minimum_count}, got {count}"
            )
        results.append(
            ListCheckResult(
                name=check.name,
                url=url,
                status_code=response.status_code,
                item_count=count,
                minimum_count=check.minimum_count,
            )
        )

    return tuple(results)


def run_detail_checks(
    *,
    base_url: str,
    token: str,
    checks: tuple[DetailCheck, ...],
    fetch,
) -> tuple[DetailCheckResult, ...]:
    normalized_base_url = base_url.rstrip("/")
    results: list[DetailCheckResult] = []
    for check in checks:
        url = f"{normalized_base_url}{check.path}"
        response = fetch(
            url,
            "GET",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            raise RuntimeVerificationError(
                f"{check.name}: expected 200, got {response.status_code}"
            )
        body_text = response.body_text or ""
        if check.expected_snippet not in body_text:
            raise RuntimeVerificationError(
                f"{check.name}: expected response body to contain {check.expected_snippet!r}"
            )
        results.append(
            DetailCheckResult(
                name=check.name,
                url=url,
                status_code=response.status_code,
                expected_snippet=check.expected_snippet,
            )
        )
    return tuple(results)


def parse_json_payload(body_text: str) -> object:
    try:
        return json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise RuntimeVerificationError("response body was not valid JSON") from exc


def run_read_model_checks(
    *,
    base_url: str,
    token: str,
    fixture_path: Path,
    fetch,
) -> tuple[ReadModelCheckResult, ...]:
    normalized_base_url = base_url.rstrip("/")
    fixture = load_fixture(fixture_path)
    dispatch_plan = fixture["dispatch"]["plans"][0]
    dispatch_fleet_id = dispatch_plan["fleet_id"]
    dispatch_date = dispatch_plan["dispatch_date"]
    fleet_driver = next(
        driver
        for driver in fixture["drivers"]
        if driver["fleet_id"] == dispatch_fleet_id
    )
    linked_assignment = next(
        assignment
        for assignment in fixture["assignments"]
        if assignment["driver_id"] == fleet_driver["driver_id"]
    )
    fleet_vehicle = next(
        vehicle
        for vehicle in fixture["vehicles"]
        if vehicle["vehicle_id"] == linked_assignment["vehicle_id"]
    )
    driver_id = fixture["drivers"][0]["driver_id"]
    driver_name = fixture["drivers"][0]["name"]
    vehicle_id = fixture["vehicles"][0]["vehicle_id"]
    vehicle_plate_number = fixture["vehicles"][0]["plate_number"]
    results: list[ReadModelCheckResult] = []

    def authenticated_get(path: str) -> FetchResult:
        return fetch(
            f"{normalized_base_url}{path}",
            "GET",
            headers={"Authorization": f"Bearer {token}"},
        )

    driver_ops_path = f"/api/driver-ops/drivers/{driver_id}/"
    driver_ops_response = authenticated_get(driver_ops_path)
    if driver_ops_response.status_code != 200:
        raise RuntimeVerificationError(
            f"driver_ops_detail: expected 200, got {driver_ops_response.status_code}"
        )
    driver_ops_payload = parse_json_payload(driver_ops_response.body_text or "")
    if not isinstance(driver_ops_payload, dict):
        raise RuntimeVerificationError("driver_ops_detail: expected object response")
    if str(driver_ops_payload.get("driver_id")) != str(driver_id):
        raise RuntimeVerificationError("driver_ops_detail: driver_id mismatch")
    if str(driver_ops_payload.get("driver_name")) != str(driver_name):
        raise RuntimeVerificationError("driver_ops_detail: driver_name mismatch")
    results.append(
        ReadModelCheckResult(
            name="driver_ops_detail",
            url=f"{normalized_base_url}{driver_ops_path}",
            status_code=driver_ops_response.status_code,
            expectation=str(driver_name),
        )
    )

    vehicle_ops_path = f"/api/vehicle-ops/vehicles/{vehicle_id}/"
    vehicle_ops_response = authenticated_get(vehicle_ops_path)
    if vehicle_ops_response.status_code != 200:
        raise RuntimeVerificationError(
            f"vehicle_ops_detail: expected 200, got {vehicle_ops_response.status_code}"
        )
    vehicle_ops_payload = parse_json_payload(vehicle_ops_response.body_text or "")
    if not isinstance(vehicle_ops_payload, dict):
        raise RuntimeVerificationError("vehicle_ops_detail: expected object response")
    if str(vehicle_ops_payload.get("vehicle_id")) != str(vehicle_id):
        raise RuntimeVerificationError("vehicle_ops_detail: vehicle_id mismatch")
    if str(vehicle_ops_payload.get("plate_number")) != str(vehicle_plate_number):
        raise RuntimeVerificationError("vehicle_ops_detail: plate_number mismatch")
    results.append(
        ReadModelCheckResult(
            name="vehicle_ops_detail",
            url=f"{normalized_base_url}{vehicle_ops_path}",
            status_code=vehicle_ops_response.status_code,
            expectation=str(vehicle_plate_number),
        )
    )

    summary_path = f"/api/dispatch-ops/summary/?dispatch_date={dispatch_date}&fleet_id={dispatch_fleet_id}"
    summary_response = authenticated_get(summary_path)
    if summary_response.status_code != 200:
        raise RuntimeVerificationError(
            f"dispatch_ops_summary: expected 200, got {summary_response.status_code}"
        )
    summary_payload = parse_json_payload(summary_response.body_text or "")
    if not isinstance(summary_payload, dict):
        raise RuntimeVerificationError("dispatch_ops_summary: expected object response")
    for key in ("dispatch_date", "fleet_id", "planned_volume", "planned_assignment_count", "matched_count"):
        if key not in summary_payload:
            raise RuntimeVerificationError(f"dispatch_ops_summary: missing key {key!r}")
    if str(summary_payload["fleet_id"]) != str(dispatch_fleet_id):
        raise RuntimeVerificationError("dispatch_ops_summary: fleet_id mismatch")
    results.append(
        ReadModelCheckResult(
            name="dispatch_ops_summary",
            url=f"{normalized_base_url}{summary_path}",
            status_code=summary_response.status_code,
            expectation="summary keys present",
        )
    )

    board_path = f"/api/dispatch-ops/board/?dispatch_date={dispatch_date}&fleet_id={dispatch_fleet_id}"
    board_response = authenticated_get(board_path)
    if board_response.status_code != 200:
        raise RuntimeVerificationError(
            f"dispatch_ops_board: expected 200, got {board_response.status_code}"
        )
    board_payload = parse_json_payload(board_response.body_text or "")
    if not isinstance(board_payload, list) or not board_payload:
        raise RuntimeVerificationError("dispatch_ops_board: expected non-empty list response")
    if not any(
        row.get("plate_number") == fleet_vehicle["plate_number"]
        and row.get("planned_driver_name") == fleet_driver["name"]
        for row in board_payload
        if isinstance(row, dict)
    ):
        raise RuntimeVerificationError(
            "dispatch_ops_board: expected seeded vehicle/driver pair in board rows"
        )
    results.append(
        ReadModelCheckResult(
            name="dispatch_ops_board",
            url=f"{normalized_base_url}{board_path}",
            status_code=board_response.status_code,
            expectation=f"{fleet_vehicle['plate_number']} with {fleet_driver['name']}",
        )
    )

    latest_path = f"/api/settlement-ops/drivers/{driver_id}/latest-settlement/"
    latest_response = authenticated_get(latest_path)
    if latest_response.status_code != 200:
        raise RuntimeVerificationError(
            f"settlement_ops_driver_latest: expected 200, got {latest_response.status_code}"
        )
    latest_payload = parse_json_payload(latest_response.body_text or "")
    if not isinstance(latest_payload, dict):
        raise RuntimeVerificationError("settlement_ops_driver_latest: expected object response")
    if str(latest_payload.get("driver_id")) != str(driver_id):
        raise RuntimeVerificationError("settlement_ops_driver_latest: driver_id mismatch")
    if "latest_settlement" not in latest_payload:
        raise RuntimeVerificationError("settlement_ops_driver_latest: missing latest_settlement")
    results.append(
        ReadModelCheckResult(
            name="settlement_ops_driver_latest",
            url=f"{normalized_base_url}{latest_path}",
            status_code=latest_response.status_code,
            expectation=str(driver_id),
        )
    )

    runs_path = "/api/settlement-ops/runs/"
    runs_response = authenticated_get(runs_path)
    if runs_response.status_code != 200:
        raise RuntimeVerificationError(
            f"settlement_ops_runs: expected 200, got {runs_response.status_code}"
        )
    runs_payload = parse_json_payload(runs_response.body_text or "")
    if not isinstance(runs_payload, list) or not runs_payload:
        raise RuntimeVerificationError("settlement_ops_runs: expected non-empty list response")
    first_run = runs_payload[0]
    if not isinstance(first_run, dict) or "settlement_run_id" not in first_run:
        raise RuntimeVerificationError("settlement_ops_runs: missing settlement_run_id")
    run_detail_path = f"/api/settlement-ops/runs/{first_run['settlement_run_id']}/"
    run_detail_response = authenticated_get(run_detail_path)
    if run_detail_response.status_code != 200:
        raise RuntimeVerificationError(
            f"settlement_ops_run_detail: expected 200, got {run_detail_response.status_code}"
        )
    run_detail_payload = parse_json_payload(run_detail_response.body_text or "")
    if not isinstance(run_detail_payload, dict) or str(run_detail_payload.get("settlement_run_id")) != str(first_run["settlement_run_id"]):
        raise RuntimeVerificationError("settlement_ops_run_detail: settlement_run_id mismatch")
    results.append(
        ReadModelCheckResult(
            name="settlement_ops_run_detail",
            url=f"{normalized_base_url}{run_detail_path}",
            status_code=run_detail_response.status_code,
            expectation=str(first_run["settlement_run_id"]),
        )
    )

    items_path = "/api/settlement-ops/items/"
    items_response = authenticated_get(items_path)
    if items_response.status_code != 200:
        raise RuntimeVerificationError(
            f"settlement_ops_items: expected 200, got {items_response.status_code}"
        )
    items_payload = parse_json_payload(items_response.body_text or "")
    if not isinstance(items_payload, list) or not items_payload:
        raise RuntimeVerificationError("settlement_ops_items: expected non-empty list response")
    first_item = items_payload[0]
    if not isinstance(first_item, dict) or "settlement_item_id" not in first_item:
        raise RuntimeVerificationError("settlement_ops_items: missing settlement_item_id")
    item_detail_path = f"/api/settlement-ops/items/{first_item['settlement_item_id']}/"
    item_detail_response = authenticated_get(item_detail_path)
    if item_detail_response.status_code != 200:
        raise RuntimeVerificationError(
            f"settlement_ops_item_detail: expected 200, got {item_detail_response.status_code}"
        )
    item_detail_payload = parse_json_payload(item_detail_response.body_text or "")
    if not isinstance(item_detail_payload, dict) or str(item_detail_payload.get("settlement_item_id")) != str(first_item["settlement_item_id"]):
        raise RuntimeVerificationError("settlement_ops_item_detail: settlement_item_id mismatch")
    results.append(
        ReadModelCheckResult(
            name="settlement_ops_item_detail",
            url=f"{normalized_base_url}{item_detail_path}",
            status_code=item_detail_response.status_code,
            expectation=str(first_item["settlement_item_id"]),
        )
    )

    return tuple(results)


def run_auth_management_checks(
    *,
    base_url: str,
    token: str,
    fetch,
) -> tuple[AuthCheckResult, ...]:
    normalized_base_url = base_url.rstrip("/")
    results: list[AuthCheckResult] = []

    def authenticated_get(path: str) -> FetchResult:
        return fetch(
            f"{normalized_base_url}{path}",
            "GET",
            headers={"Authorization": f"Bearer {token}"},
        )

    checks = (
        (
            "identity_me",
            "/api/auth/identity-me/",
            lambda payload: isinstance(payload, dict)
            and payload.get("identity")
            and payload.get("session_kind") == "normal"
            and payload.get("active_account"),
            "normal session payload",
        ),
        (
            "identity_profile",
            "/api/auth/identity-profile/",
            lambda payload: isinstance(payload, dict)
            and payload.get("name")
            and payload.get("birth_date"),
            "profile keys present",
        ),
        (
            "identity_login_methods",
            "/api/auth/identity-login-methods/",
            lambda payload: isinstance(payload, dict)
            and isinstance(payload.get("methods"), list)
            and len(payload["methods"]) >= 1,
            "at least one login method",
        ),
        (
            "identity_requests_me",
            "/api/auth/identity-signup-requests/me/",
            lambda payload: isinstance(payload, dict) and "requests" in payload,
            "self-service request list",
        ),
        (
            "identity_requests_manage",
            "/api/auth/identity-signup-requests/manage/?status=pending",
            lambda payload: isinstance(payload, dict) and "requests" in payload,
            "managed request list",
        ),
        (
            "manager_accounts_manage",
            "/api/auth/manager-accounts/manage/",
            lambda payload: isinstance(payload, dict)
            and isinstance(payload.get("accounts"), list),
            "manager account list",
        ),
    )

    for name, path, validator, expectation in checks:
        response = authenticated_get(path)
        if response.status_code != 200:
            raise RuntimeVerificationError(
                f"{name}: expected 200, got {response.status_code}"
            )
        payload = parse_json_payload(response.body_text or "")
        if not validator(payload):
            raise RuntimeVerificationError(f"{name}: expectation failed")
        results.append(
            AuthCheckResult(
                name=name,
                url=f"{normalized_base_url}{path}",
                status_code=response.status_code,
                expectation=expectation,
            )
        )

    return tuple(results)


def run_write_checks(
    *,
    base_url: str,
    token: str,
    fixture_path: Path,
    fetch,
) -> tuple[WriteCheckResult, ...]:
    normalized_base_url = base_url.rstrip("/")
    results: list[WriteCheckResult] = []
    smoke_suffix = uuid.uuid4().hex[:10]
    fixture = load_fixture(fixture_path)
    first_company = fixture["organizations"][0]
    first_fleet = first_company["fleets"][0]
    first_dispatch_plan = fixture["dispatch"]["plans"][0]
    first_driver = fixture["drivers"][0]

    def authenticated_post(path: str, payload: dict[str, object]) -> FetchResult:
        return fetch(
            f"{normalized_base_url}{path}",
            "POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            body_bytes=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

    def authenticated_get(path: str) -> FetchResult:
        return fetch(
            f"{normalized_base_url}{path}",
            "GET",
            headers={"Authorization": f"Bearer {token}"},
        )

    def authenticated_patch(path: str, payload: dict[str, object]) -> FetchResult:
        return fetch(
            f"{normalized_base_url}{path}",
            "PATCH",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            body_bytes=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

    def authenticated_post_empty(path: str) -> FetchResult:
        return fetch(
            f"{normalized_base_url}{path}",
            "POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            body_bytes=None,
        )

    announcement_slug = f"ops-smoke-announcement-{smoke_suffix}"
    announcement_title = f"Ops smoke announcement {smoke_suffix}"
    announcement_response = authenticated_post(
        "/api/announcements/",
        {
            "slug": announcement_slug,
            "title": announcement_title,
            "body": f"Ops smoke announcement body {smoke_suffix}",
            "status": "draft",
            "exposure_scope": "all",
            "is_pinned": False,
            "display_order": 999,
        },
    )
    if announcement_response.status_code != 201:
        raise RuntimeVerificationError(
            f"announcement_create: expected 201, got {announcement_response.status_code}"
        )
    announcement_payload = parse_json_payload(announcement_response.body_text or "")
    if not isinstance(announcement_payload, dict) or str(announcement_payload.get("title")) != announcement_title:
        raise RuntimeVerificationError("announcement_create: created title mismatch")
    created_announcement_id = str(announcement_payload.get("announcement_id", ""))
    results.append(
        WriteCheckResult(
            name="announcement_create",
            url=f"{normalized_base_url}/api/announcements/",
            status_code=announcement_response.status_code,
            expectation=announcement_title,
        )
    )

    announcement_patch_response = authenticated_patch(
        f"/api/announcements/{created_announcement_id}/",
        {"status": "archived"},
    )
    if announcement_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"announcement_patch: expected 200, got {announcement_patch_response.status_code}"
        )
    announcement_patch_payload = parse_json_payload(announcement_patch_response.body_text or "")
    if not isinstance(announcement_patch_payload, dict) or str(announcement_patch_payload.get("status")) != "archived":
        raise RuntimeVerificationError("announcement_patch: patched status mismatch")
    results.append(
        WriteCheckResult(
            name="announcement_patch",
            url=f"{normalized_base_url}/api/announcements/{created_announcement_id}/",
            status_code=announcement_patch_response.status_code,
            expectation="archived",
        )
    )

    support_body = f"ops smoke support reply {smoke_suffix}"
    support_response = authenticated_post(
        "/api/ticket/ticket-responses/",
        {
            "ticket_id": OPEN_SUPPORT_TICKET_ID,
            "body": support_body,
        },
    )
    if support_response.status_code != 201:
        raise RuntimeVerificationError(
            f"support_reply_create: expected 201, got {support_response.status_code}"
        )
    support_payload = parse_json_payload(support_response.body_text or "")
    if not isinstance(support_payload, dict) or str(support_payload.get("ticket_id")) != str(OPEN_SUPPORT_TICKET_ID):
        raise RuntimeVerificationError("support_reply_create: ticket_id mismatch")
    if str(support_payload.get("body")) != support_body:
        raise RuntimeVerificationError("support_reply_create: created body mismatch")
    results.append(
        WriteCheckResult(
            name="support_reply_create",
            url=f"{normalized_base_url}/api/ticket/ticket-responses/",
            status_code=support_response.status_code,
            expectation=support_body,
        )
    )

    support_ticket_patch_response = authenticated_patch(
        f"/api/ticket/tickets/{OPEN_SUPPORT_TICKET_ID}/",
        {
            "status": "in_progress",
            "priority": "high",
        },
    )
    if support_ticket_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"support_ticket_patch: expected 200, got {support_ticket_patch_response.status_code}"
        )
    support_ticket_patch_payload = parse_json_payload(support_ticket_patch_response.body_text or "")
    if not isinstance(support_ticket_patch_payload, dict):
        raise RuntimeVerificationError("support_ticket_patch: expected object response")
    if str(support_ticket_patch_payload.get("status")) != "in_progress":
        raise RuntimeVerificationError("support_ticket_patch: patched status mismatch")
    if str(support_ticket_patch_payload.get("priority")) != "high":
        raise RuntimeVerificationError("support_ticket_patch: patched priority mismatch")
    results.append(
        WriteCheckResult(
            name="support_ticket_patch",
            url=f"{normalized_base_url}/api/ticket/tickets/{OPEN_SUPPORT_TICKET_ID}/",
            status_code=support_ticket_patch_response.status_code,
            expectation="in_progress/high",
        )
    )

    identity_me_response = authenticated_get("/api/auth/identity-me/")
    if identity_me_response.status_code != 200:
        raise RuntimeVerificationError(
            f"identity_me_for_notification_create: expected 200, got {identity_me_response.status_code}"
        )
    identity_me_payload = parse_json_payload(identity_me_response.body_text or "")
    if not isinstance(identity_me_payload, dict):
        raise RuntimeVerificationError("identity_me_for_notification_create: expected object response")
    active_account = identity_me_payload.get("active_account")
    if not isinstance(active_account, dict) or not active_account.get("account_id"):
        raise RuntimeVerificationError("identity_me_for_notification_create: active_account.account_id missing")
    recipient_account_id = str(active_account["account_id"])

    notification_title = f"Ops smoke notification {smoke_suffix}"
    notification_response = authenticated_post(
        "/api/notifications/general/",
        {
            "recipient_account_id": recipient_account_id,
            "category": "announcement",
            "source_type": "ops_smoke",
            "source_ref": smoke_suffix,
            "title": notification_title,
            "body": f"Ops smoke notification body {smoke_suffix}",
            "status": "unread",
        },
    )
    if notification_response.status_code != 201:
        raise RuntimeVerificationError(
            f"general_notification_create: expected 201, got {notification_response.status_code}"
        )
    notification_payload = parse_json_payload(notification_response.body_text or "")
    if not isinstance(notification_payload, dict) or str(notification_payload.get("title")) != notification_title:
        raise RuntimeVerificationError("general_notification_create: created title mismatch")
    created_notification_id = str(notification_payload.get("notification_id", ""))
    results.append(
        WriteCheckResult(
            name="general_notification_create",
            url=f"{normalized_base_url}/api/notifications/general/",
            status_code=notification_response.status_code,
            expectation=notification_title,
        )
    )

    notification_patch_response = authenticated_patch(
        f"/api/notifications/general/{created_notification_id}/",
        {"status": "read"},
    )
    if notification_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"general_notification_patch: expected 200, got {notification_patch_response.status_code}"
        )
    notification_patch_payload = parse_json_payload(notification_patch_response.body_text or "")
    if not isinstance(notification_patch_payload, dict):
        raise RuntimeVerificationError("general_notification_patch: expected object response")
    if str(notification_patch_payload.get("status")) != "read":
        raise RuntimeVerificationError("general_notification_patch: patched status mismatch")
    if not notification_patch_payload.get("read_at"):
        raise RuntimeVerificationError("general_notification_patch: read_at missing")
    results.append(
        WriteCheckResult(
            name="general_notification_patch",
            url=f"{normalized_base_url}/api/notifications/general/{created_notification_id}/",
            status_code=notification_patch_response.status_code,
            expectation="read",
        )
    )

    outsourced_driver_name = f"Ops Smoke Outsourced {smoke_suffix}"
    outsourced_driver_response = authenticated_post(
        "/api/dispatch/outsourced-drivers/",
        {
            "dispatch_plan_id": str(first_dispatch_plan["dispatch_plan_id"]),
            "name": outsourced_driver_name,
            "contact_number": "010-9999-0000",
            "vehicle_note": "smoke van",
            "memo": "initial outsourced memo",
        },
    )
    if outsourced_driver_response.status_code != 201:
        raise RuntimeVerificationError(
            f"outsourced_driver_create: expected 201, got {outsourced_driver_response.status_code}"
        )
    outsourced_driver_payload = parse_json_payload(outsourced_driver_response.body_text or "")
    if not isinstance(outsourced_driver_payload, dict) or str(outsourced_driver_payload.get("name")) != outsourced_driver_name:
        raise RuntimeVerificationError("outsourced_driver_create: created name mismatch")
    created_outsourced_driver_id = str(outsourced_driver_payload.get("outsourced_driver_id", ""))
    results.append(
        WriteCheckResult(
            name="outsourced_driver_create",
            url=f"{normalized_base_url}/api/dispatch/outsourced-drivers/",
            status_code=outsourced_driver_response.status_code,
            expectation=outsourced_driver_name,
        )
    )

    outsourced_driver_patch_response = authenticated_patch(
        f"/api/dispatch/outsourced-drivers/{created_outsourced_driver_id}/",
        {"memo": "patched outsourced memo"},
    )
    if outsourced_driver_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"outsourced_driver_patch: expected 200, got {outsourced_driver_patch_response.status_code}"
        )
    outsourced_driver_patch_payload = parse_json_payload(outsourced_driver_patch_response.body_text or "")
    if not isinstance(outsourced_driver_patch_payload, dict) or str(outsourced_driver_patch_payload.get("memo")) != "patched outsourced memo":
        raise RuntimeVerificationError("outsourced_driver_patch: patched memo mismatch")
    results.append(
        WriteCheckResult(
            name="outsourced_driver_patch",
            url=f"{normalized_base_url}/api/dispatch/outsourced-drivers/{created_outsourced_driver_id}/",
            status_code=outsourced_driver_patch_response.status_code,
            expectation="patched outsourced memo",
        )
    )

    bootstrap_response = authenticated_post(
        "/api/delivery-record/daily-snapshots/bootstrap-from-dispatch/",
        {
            "company_id": str(first_company["company_id"]),
            "fleet_id": str(first_fleet["fleet_id"]),
            "service_date": str(first_dispatch_plan["dispatch_date"]),
        },
    )
    if bootstrap_response.status_code != 200:
        raise RuntimeVerificationError(
            f"dispatch_snapshot_bootstrap: expected 200, got {bootstrap_response.status_code}"
        )
    bootstrap_payload = parse_json_payload(bootstrap_response.body_text or "")
    if not isinstance(bootstrap_payload, dict):
        raise RuntimeVerificationError("dispatch_snapshot_bootstrap: expected object response")
    created_count = int(bootstrap_payload.get("created_count", 0))
    skipped_count = int(bootstrap_payload.get("skipped_count", 0))
    if created_count + skipped_count < 1:
        raise RuntimeVerificationError(
            "dispatch_snapshot_bootstrap: expected at least one created or skipped snapshot"
        )
    results.append(
        WriteCheckResult(
            name="dispatch_snapshot_bootstrap",
            url=f"{normalized_base_url}/api/delivery-record/daily-snapshots/bootstrap-from-dispatch/",
            status_code=bootstrap_response.status_code,
            expectation=f"created={created_count}, skipped={skipped_count}",
        )
    )

    outsourced_driver_archive_response = authenticated_post_empty(
        f"/api/dispatch/outsourced-drivers/{created_outsourced_driver_id}/archive/"
    )
    if outsourced_driver_archive_response.status_code != 200:
        raise RuntimeVerificationError(
            f"outsourced_driver_archive: expected 200, got {outsourced_driver_archive_response.status_code}"
        )
    outsourced_driver_archive_payload = parse_json_payload(outsourced_driver_archive_response.body_text or "")
    if not isinstance(outsourced_driver_archive_payload, dict) or str(outsourced_driver_archive_payload.get("status")) != "archived":
        raise RuntimeVerificationError("outsourced_driver_archive: patched status mismatch")
    results.append(
        WriteCheckResult(
            name="outsourced_driver_archive",
            url=f"{normalized_base_url}/api/dispatch/outsourced-drivers/{created_outsourced_driver_id}/archive/",
            status_code=outsourced_driver_archive_response.status_code,
            expectation="archived",
        )
    )

    settlement_period_start = str(first_dispatch_plan["dispatch_date"])
    settlement_run_response = authenticated_post(
        "/api/settlements/runs/",
        {
            "company_id": str(first_company["company_id"]),
            "fleet_id": str(first_fleet["fleet_id"]),
            "period_start": settlement_period_start,
            "period_end": settlement_period_start,
            "status": "draft",
        },
    )
    if settlement_run_response.status_code != 201:
        raise RuntimeVerificationError(
            f"settlement_run_create: expected 201, got {settlement_run_response.status_code}"
        )
    settlement_run_payload = parse_json_payload(settlement_run_response.body_text or "")
    if not isinstance(settlement_run_payload, dict) or str(settlement_run_payload.get("status")) != "draft":
        raise RuntimeVerificationError("settlement_run_create: created status mismatch")
    results.append(
        WriteCheckResult(
            name="settlement_run_create",
            url=f"{normalized_base_url}/api/settlements/runs/",
            status_code=settlement_run_response.status_code,
            expectation=str(settlement_run_payload.get("settlement_run_id", "draft")),
        )
    )

    created_run_id = str(settlement_run_payload.get("settlement_run_id", ""))
    settlement_item_response = authenticated_post(
        "/api/settlements/items/",
        {
            "settlement_run_id": created_run_id,
            "driver_id": str(first_driver["driver_id"]),
            "amount": "125000.50",
            "payout_status": "pending",
        },
    )
    if settlement_item_response.status_code != 201:
        raise RuntimeVerificationError(
            f"settlement_item_create: expected 201, got {settlement_item_response.status_code}"
        )
    settlement_item_payload = parse_json_payload(settlement_item_response.body_text or "")
    if not isinstance(settlement_item_payload, dict):
        raise RuntimeVerificationError("settlement_item_create: expected object response")
    if str(settlement_item_payload.get("settlement_run_id")) != created_run_id:
        raise RuntimeVerificationError("settlement_item_create: settlement_run_id mismatch")
    if str(settlement_item_payload.get("driver_id")) != str(first_driver["driver_id"]):
        raise RuntimeVerificationError("settlement_item_create: driver_id mismatch")
    results.append(
        WriteCheckResult(
            name="settlement_item_create",
            url=f"{normalized_base_url}/api/settlements/items/",
            status_code=settlement_item_response.status_code,
            expectation=str(settlement_item_payload.get("settlement_item_id", "")),
        )
    )

    settlement_run_patch_response = authenticated_patch(
        f"/api/settlements/runs/{created_run_id}/",
        {"status": "reviewed"},
    )
    if settlement_run_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"settlement_run_patch: expected 200, got {settlement_run_patch_response.status_code}"
        )
    settlement_run_patch_payload = parse_json_payload(settlement_run_patch_response.body_text or "")
    if not isinstance(settlement_run_patch_payload, dict) or str(settlement_run_patch_payload.get("status")) != "reviewed":
        raise RuntimeVerificationError("settlement_run_patch: patched status mismatch")
    results.append(
        WriteCheckResult(
            name="settlement_run_patch",
            url=f"{normalized_base_url}/api/settlements/runs/{created_run_id}/",
            status_code=settlement_run_patch_response.status_code,
            expectation="reviewed",
        )
    )

    created_item_id = str(settlement_item_payload.get("settlement_item_id", ""))
    settlement_item_patch_response = authenticated_patch(
        f"/api/settlements/items/{created_item_id}/",
        {"payout_status": "paid"},
    )
    if settlement_item_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"settlement_item_patch: expected 200, got {settlement_item_patch_response.status_code}"
        )
    settlement_item_patch_payload = parse_json_payload(settlement_item_patch_response.body_text or "")
    if not isinstance(settlement_item_patch_payload, dict) or str(settlement_item_patch_payload.get("payout_status")) != "paid":
        raise RuntimeVerificationError("settlement_item_patch: patched payout_status mismatch")
    results.append(
        WriteCheckResult(
            name="settlement_item_patch",
            url=f"{normalized_base_url}/api/settlements/items/{created_item_id}/",
            status_code=settlement_item_patch_response.status_code,
            expectation="paid",
        )
    )

    personnel_document_title = f"Ops Smoke Document {smoke_suffix}"
    personnel_document_response = authenticated_post(
        "/api/personnel-documents/documents/",
        {
            "driver_id": str(first_driver["driver_id"]),
            "document_type": "contract",
            "status": "draft",
            "title": personnel_document_title,
            "document_number": f"OPS-SMOKE-{smoke_suffix}",
            "issuer_name": "CLEVER",
            "issued_on": settlement_period_start,
            "expires_on": settlement_period_start,
            "notes": "initial personnel document note",
            "external_reference": f"ops://personnel/{smoke_suffix}",
            "payload": {"signed": False},
        },
    )
    if personnel_document_response.status_code != 201:
        raise RuntimeVerificationError(
            f"personnel_document_create: expected 201, got {personnel_document_response.status_code}"
        )
    personnel_document_payload = parse_json_payload(personnel_document_response.body_text or "")
    if not isinstance(personnel_document_payload, dict) or str(personnel_document_payload.get("title")) != personnel_document_title:
        raise RuntimeVerificationError("personnel_document_create: created title mismatch")
    created_personnel_document_id = str(personnel_document_payload.get("personnel_document_id", ""))
    results.append(
        WriteCheckResult(
            name="personnel_document_create",
            url=f"{normalized_base_url}/api/personnel-documents/documents/",
            status_code=personnel_document_response.status_code,
            expectation=personnel_document_title,
        )
    )

    personnel_document_patch_response = authenticated_patch(
        f"/api/personnel-documents/documents/{created_personnel_document_id}/",
        {
            "status": "active",
            "notes": "patched personnel document note",
        },
    )
    if personnel_document_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"personnel_document_patch: expected 200, got {personnel_document_patch_response.status_code}"
        )
    personnel_document_patch_payload = parse_json_payload(personnel_document_patch_response.body_text or "")
    if not isinstance(personnel_document_patch_payload, dict):
        raise RuntimeVerificationError("personnel_document_patch: expected object response")
    if str(personnel_document_patch_payload.get("status")) != "active":
        raise RuntimeVerificationError("personnel_document_patch: patched status mismatch")
    if str(personnel_document_patch_payload.get("notes")) != "patched personnel document note":
        raise RuntimeVerificationError("personnel_document_patch: patched notes mismatch")
    results.append(
        WriteCheckResult(
            name="personnel_document_patch",
            url=f"{normalized_base_url}/api/personnel-documents/documents/{created_personnel_document_id}/",
            status_code=personnel_document_patch_response.status_code,
            expectation="active",
        )
    )

    region_code = f"ops-smoke-region-{smoke_suffix}"
    region_response = authenticated_post(
        "/api/regions/",
        {
            "region_code": region_code,
            "name": f"Ops Smoke Region {smoke_suffix}",
            "status": "draft",
            "difficulty_level": "medium",
            "polygon_geojson": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [126.97, 37.56],
                        [126.99, 37.56],
                        [126.99, 37.58],
                        [126.97, 37.58],
                        [126.97, 37.56],
                    ]
                ],
            },
            "description": "ops smoke region",
            "display_order": 99,
        },
    )
    if region_response.status_code != 201:
        raise RuntimeVerificationError(
            f"region_create: expected 201, got {region_response.status_code}"
        )
    region_payload = parse_json_payload(region_response.body_text or "")
    if not isinstance(region_payload, dict) or str(region_payload.get("region_code")) != region_code:
        raise RuntimeVerificationError("region_create: created region_code mismatch")
    created_region_id = str(region_payload.get("region_id", ""))
    results.append(
        WriteCheckResult(
            name="region_create",
            url=f"{normalized_base_url}/api/regions/",
            status_code=region_response.status_code,
            expectation=region_code,
        )
    )

    region_patch_response = authenticated_patch(
        f"/api/regions/{created_region_id}/",
        {
            "status": "active",
            "display_order": 77,
        },
    )
    if region_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"region_patch: expected 200, got {region_patch_response.status_code}"
        )
    region_patch_payload = parse_json_payload(region_patch_response.body_text or "")
    if not isinstance(region_patch_payload, dict):
        raise RuntimeVerificationError("region_patch: expected object response")
    if str(region_patch_payload.get("status")) != "active":
        raise RuntimeVerificationError("region_patch: patched status mismatch")
    if int(region_patch_payload.get("display_order", -1)) != 77:
        raise RuntimeVerificationError("region_patch: patched display_order mismatch")
    results.append(
        WriteCheckResult(
            name="region_patch",
            url=f"{normalized_base_url}/api/regions/{created_region_id}/",
            status_code=region_patch_response.status_code,
            expectation="active/77",
        )
    )

    company_name = f"Ops Smoke Company {smoke_suffix}"
    company_response = authenticated_post(
        "/api/org/companies/",
        {"name": company_name},
    )
    if company_response.status_code != 201:
        raise RuntimeVerificationError(
            f"company_create: expected 201, got {company_response.status_code}"
        )
    company_payload = parse_json_payload(company_response.body_text or "")
    if not isinstance(company_payload, dict) or str(company_payload.get("name")) != company_name:
        raise RuntimeVerificationError("company_create: created name mismatch")
    created_company_id = str(company_payload.get("company_id", ""))
    created_company_route_no = str(company_payload.get("route_no", ""))
    results.append(
        WriteCheckResult(
            name="company_create",
            url=f"{normalized_base_url}/api/org/companies/",
            status_code=company_response.status_code,
            expectation=company_name,
        )
    )

    fleet_name = f"Ops Smoke Fleet {smoke_suffix}"
    fleet_response = authenticated_post(
        "/api/org/fleets/",
        {
            "name": fleet_name,
            "company_id": created_company_id,
        },
    )
    if fleet_response.status_code != 201:
        raise RuntimeVerificationError(
            f"fleet_create: expected 201, got {fleet_response.status_code}"
        )
    fleet_payload = parse_json_payload(fleet_response.body_text or "")
    if not isinstance(fleet_payload, dict) or str(fleet_payload.get("name")) != fleet_name:
        raise RuntimeVerificationError("fleet_create: created name mismatch")
    created_fleet_route_no = str(fleet_payload.get("route_no", ""))
    results.append(
        WriteCheckResult(
            name="fleet_create",
            url=f"{normalized_base_url}/api/org/fleets/",
            status_code=fleet_response.status_code,
            expectation=fleet_name,
        )
    )

    company_patch_response = authenticated_patch(
        f"/api/org/companies/{created_company_route_no}/",
        {"name": "Ops Smoke Company Updated"},
    )
    if company_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"company_patch: expected 200, got {company_patch_response.status_code}"
        )
    company_patch_payload = parse_json_payload(company_patch_response.body_text or "")
    if not isinstance(company_patch_payload, dict) or str(company_patch_payload.get("name")) != "Ops Smoke Company Updated":
        raise RuntimeVerificationError("company_patch: patched name mismatch")
    results.append(
        WriteCheckResult(
            name="company_patch",
            url=f"{normalized_base_url}/api/org/companies/{created_company_route_no}/",
            status_code=company_patch_response.status_code,
            expectation="Ops Smoke Company Updated",
        )
    )

    fleet_patch_response = authenticated_patch(
        f"/api/org/fleets/{created_fleet_route_no}/",
        {"name": "Ops Smoke Fleet Updated"},
    )
    if fleet_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"fleet_patch: expected 200, got {fleet_patch_response.status_code}"
        )
    fleet_patch_payload = parse_json_payload(fleet_patch_response.body_text or "")
    if not isinstance(fleet_patch_payload, dict) or str(fleet_patch_payload.get("name")) != "Ops Smoke Fleet Updated":
        raise RuntimeVerificationError("fleet_patch: patched name mismatch")
    results.append(
        WriteCheckResult(
            name="fleet_patch",
            url=f"{normalized_base_url}/api/org/fleets/{created_fleet_route_no}/",
            status_code=fleet_patch_response.status_code,
            expectation="Ops Smoke Fleet Updated",
        )
    )

    driver_name = f"Ops Smoke Driver {smoke_suffix}"
    driver_response = authenticated_post(
        "/api/drivers/",
        {
            "company_id": str(first_company["company_id"]),
            "fleet_id": str(first_fleet["fleet_id"]),
            "name": driver_name,
            "ev_id": f"OPS-SMOKE-{smoke_suffix.upper()}",
            "phone_number": "010-7777-6666",
            "address": "Seoul Smoke Route",
            "employment_status": "active",
            "qualification_status": "qualified",
        },
    )
    if driver_response.status_code != 201:
        raise RuntimeVerificationError(
            f"driver_create: expected 201, got {driver_response.status_code}"
        )
    driver_payload = parse_json_payload(driver_response.body_text or "")
    if not isinstance(driver_payload, dict) or str(driver_payload.get("name")) != driver_name:
        raise RuntimeVerificationError("driver_create: created name mismatch")
    created_driver_id = str(driver_payload.get("driver_id", ""))
    created_driver_route_no = str(driver_payload.get("route_no", ""))
    results.append(
        WriteCheckResult(
            name="driver_create",
            url=f"{normalized_base_url}/api/drivers/",
            status_code=driver_response.status_code,
            expectation=driver_name,
        )
    )

    driver_patch_response = authenticated_patch(
        f"/api/drivers/{created_driver_route_no}/",
        {"phone_number": "010-8888-7777"},
    )
    if driver_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"driver_patch: expected 200, got {driver_patch_response.status_code}"
        )
    driver_patch_payload = parse_json_payload(driver_patch_response.body_text or "")
    if not isinstance(driver_patch_payload, dict) or str(driver_patch_payload.get("phone_number")) != "010-8888-7777":
        raise RuntimeVerificationError("driver_patch: patched phone_number mismatch")
    results.append(
        WriteCheckResult(
            name="driver_patch",
            url=f"{normalized_base_url}/api/drivers/{created_driver_route_no}/",
            status_code=driver_patch_response.status_code,
            expectation="010-8888-7777",
        )
    )

    vehicle_plate_number = f"90가{smoke_suffix[:4]}"
    vehicle_response = authenticated_post(
        "/api/vehicles/vehicle-masters/",
        {
            "manufacturer_company_id": str(first_company["company_id"]),
            "plate_number": vehicle_plate_number,
            "vin": f"SMOKEVIN{smoke_suffix.upper():0<10}"[:17],
            "manufacturer_vehicle_code": f"OPS-SMOKE-{smoke_suffix[:6].upper()}",
            "model_name": "Ops Smoke Cargo Van",
            "vehicle_status": "active",
        },
    )
    if vehicle_response.status_code != 201:
        raise RuntimeVerificationError(
            f"vehicle_create: expected 201, got {vehicle_response.status_code}"
        )
    vehicle_payload = parse_json_payload(vehicle_response.body_text or "")
    if not isinstance(vehicle_payload, dict) or str(vehicle_payload.get("plate_number")) != vehicle_plate_number:
        raise RuntimeVerificationError("vehicle_create: created plate_number mismatch")
    created_vehicle_id = str(vehicle_payload.get("vehicle_id", ""))
    created_vehicle_route_no = str(vehicle_payload.get("route_no", ""))
    results.append(
        WriteCheckResult(
            name="vehicle_create",
            url=f"{normalized_base_url}/api/vehicles/vehicle-masters/",
            status_code=vehicle_response.status_code,
            expectation=vehicle_plate_number,
        )
    )

    vehicle_patch_response = authenticated_patch(
        f"/api/vehicles/vehicle-masters/{created_vehicle_route_no}/",
        {"model_name": "Ops Smoke Cargo Van Updated"},
    )
    if vehicle_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"vehicle_patch: expected 200, got {vehicle_patch_response.status_code}"
        )
    vehicle_patch_payload = parse_json_payload(vehicle_patch_response.body_text or "")
    if not isinstance(vehicle_patch_payload, dict) or str(vehicle_patch_payload.get("model_name")) != "Ops Smoke Cargo Van Updated":
        raise RuntimeVerificationError("vehicle_patch: patched model_name mismatch")
    results.append(
        WriteCheckResult(
            name="vehicle_patch",
            url=f"{normalized_base_url}/api/vehicles/vehicle-masters/{created_vehicle_route_no}/",
            status_code=vehicle_patch_response.status_code,
            expectation="Ops Smoke Cargo Van Updated",
        )
    )

    vehicle_operator_access_response = authenticated_post(
        "/api/vehicles/vehicle-operator-accesses/",
        {
            "vehicle_id": created_vehicle_id,
            "operator_company_id": str(first_company["company_id"]),
            "access_status": "active",
            "started_at": "2026-04-06T09:00:00Z",
            "ended_at": None,
        },
    )
    if vehicle_operator_access_response.status_code != 201:
        raise RuntimeVerificationError(
            f"vehicle_operator_access_create: expected 201, got {vehicle_operator_access_response.status_code}"
        )
    vehicle_operator_access_payload = parse_json_payload(vehicle_operator_access_response.body_text or "")
    if not isinstance(vehicle_operator_access_payload, dict) or str(vehicle_operator_access_payload.get("access_status")) != "active":
        raise RuntimeVerificationError("vehicle_operator_access_create: created access_status mismatch")
    created_vehicle_operator_access_id = str(
        vehicle_operator_access_payload.get("vehicle_operator_access_id", "")
    )
    results.append(
        WriteCheckResult(
            name="vehicle_operator_access_create",
            url=f"{normalized_base_url}/api/vehicles/vehicle-operator-accesses/",
            status_code=vehicle_operator_access_response.status_code,
            expectation="active",
        )
    )

    assignment_response = authenticated_post(
        "/api/driver-vehicle-assignments/assignments/",
        {
            "driver_id": created_driver_id,
            "vehicle_id": created_vehicle_id,
            "operator_company_id": str(first_company["company_id"]),
            "assignment_status": "assigned",
            "assigned_at": "2026-04-06T09:15:00Z",
            "unassigned_at": None,
        },
    )
    if assignment_response.status_code != 201:
        raise RuntimeVerificationError(
            f"assignment_create: expected 201, got {assignment_response.status_code}"
        )
    assignment_payload = parse_json_payload(assignment_response.body_text or "")
    if not isinstance(assignment_payload, dict) or str(assignment_payload.get("assignment_status")) != "assigned":
        raise RuntimeVerificationError("assignment_create: created assignment_status mismatch")
    created_assignment_route_no = str(assignment_payload.get("route_no", ""))
    results.append(
        WriteCheckResult(
            name="assignment_create",
            url=f"{normalized_base_url}/api/driver-vehicle-assignments/assignments/",
            status_code=assignment_response.status_code,
            expectation="assigned",
        )
    )

    assignment_patch_response = authenticated_patch(
        f"/api/driver-vehicle-assignments/assignments/{created_assignment_route_no}/",
        {
            "assignment_status": "unassigned",
            "unassigned_at": "2026-04-06T09:30:00Z",
        },
    )
    if assignment_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"assignment_patch: expected 200, got {assignment_patch_response.status_code}"
        )
    assignment_patch_payload = parse_json_payload(assignment_patch_response.body_text or "")
    if not isinstance(assignment_patch_payload, dict) or str(assignment_patch_payload.get("assignment_status")) != "unassigned":
        raise RuntimeVerificationError("assignment_patch: patched assignment_status mismatch")
    results.append(
        WriteCheckResult(
            name="assignment_patch",
            url=f"{normalized_base_url}/api/driver-vehicle-assignments/assignments/{created_assignment_route_no}/",
            status_code=assignment_patch_response.status_code,
            expectation="unassigned",
        )
    )

    vehicle_operator_access_patch_response = authenticated_patch(
        f"/api/vehicles/vehicle-operator-accesses/{created_vehicle_operator_access_id}/",
        {
            "access_status": "suspended",
            "ended_at": "2026-04-06T10:00:00Z",
        },
    )
    if vehicle_operator_access_patch_response.status_code != 200:
        raise RuntimeVerificationError(
            f"vehicle_operator_access_patch: expected 200, got {vehicle_operator_access_patch_response.status_code}"
        )
    vehicle_operator_access_patch_payload = parse_json_payload(
        vehicle_operator_access_patch_response.body_text or ""
    )
    if not isinstance(vehicle_operator_access_patch_payload, dict) or str(vehicle_operator_access_patch_payload.get("access_status")) != "suspended":
        raise RuntimeVerificationError("vehicle_operator_access_patch: patched access_status mismatch")
    results.append(
        WriteCheckResult(
            name="vehicle_operator_access_patch",
            url=f"{normalized_base_url}/api/vehicles/vehicle-operator-accesses/{created_vehicle_operator_access_id}/",
            status_code=vehicle_operator_access_patch_response.status_code,
            expectation="suspended",
        )
    )

    return tuple(results)


def authenticate(*, base_url: str, email: str, password: str, fetch) -> str:
    body_bytes = json.dumps({"email": email, "password": password}).encode("utf-8")
    response = fetch(
        f"{base_url}/api/auth/identity-login/",
        "POST",
        headers={"Content-Type": "application/json"},
        body_bytes=body_bytes,
    )
    if response.status_code != 200:
        raise RuntimeVerificationError(
            f"identity-login: expected 200, got {response.status_code}"
        )
    try:
        payload = json.loads(response.body_text or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeVerificationError("identity-login: response body was not valid JSON") from exc
    token = payload.get("access_token")
    if not token:
        raise RuntimeVerificationError("identity-login: access_token missing")
    return token


def extract_item_count(body_text: str) -> int:
    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise RuntimeVerificationError("list response was not valid JSON") from exc

    if isinstance(payload, list):
        return len(payload)
    if not isinstance(payload, dict):
        raise RuntimeVerificationError("list response JSON was neither object nor list")

    for key in ("results", "items", "runs", "records", "entries", "data", "companies", "drivers", "vehicles"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)

    raise RuntimeVerificationError(
        f"list response JSON did not contain a supported collection key: {', '.join(payload.keys())}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that the local stack exposes ops-derived fixture data after authenticated login.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--fixture-path", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--email", default=DEFAULT_ADMIN_EMAIL)
    parser.add_argument("--password", default=DEFAULT_ADMIN_PASSWORD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fetch = build_fetch()
    token = authenticate(
        base_url=args.base_url.rstrip("/"),
        email=args.email,
        password=args.password,
        fetch=fetch,
    )
    list_results = run_list_checks(
        base_url=args.base_url,
        email=args.email,
        password=args.password,
        fixture_path=args.fixture_path,
        fetch=fetch,
    )
    detail_results = run_detail_checks(
        base_url=args.base_url,
        token=token,
        checks=build_detail_checks(args.fixture_path) + build_seeded_detail_checks(),
        fetch=fetch,
    )
    auth_management_results = run_auth_management_checks(
        base_url=args.base_url,
        token=token,
        fetch=fetch,
    )
    write_results = run_write_checks(
        base_url=args.base_url,
        token=token,
        fixture_path=args.fixture_path,
        fetch=fetch,
    )
    read_model_results = run_read_model_checks(
        base_url=args.base_url,
        token=token,
        fixture_path=args.fixture_path,
        fetch=fetch,
    )
    print(
        json.dumps(
            {
                "lists": [
                    {
                        "name": result.name,
                        "url": result.url,
                        "status_code": result.status_code,
                        "item_count": result.item_count,
                        "minimum_count": result.minimum_count,
                    }
                    for result in list_results
                ],
                "details": [
                    {
                        "name": result.name,
                        "url": result.url,
                        "status_code": result.status_code,
                        "expected_snippet": result.expected_snippet,
                    }
                    for result in detail_results
                ],
                "auth_management": [
                    {
                        "name": result.name,
                        "url": result.url,
                        "status_code": result.status_code,
                        "expectation": result.expectation,
                    }
                    for result in auth_management_results
                ],
                "writes": [
                    {
                        "name": result.name,
                        "url": result.url,
                        "status_code": result.status_code,
                        "expectation": result.expectation,
                    }
                    for result in write_results
                ],
                "read_models": [
                    {
                        "name": result.name,
                        "url": result.url,
                        "status_code": result.status_code,
                        "expectation": result.expectation,
                    }
                    for result in read_model_results
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _legacy_main_output_for_reference(
    *,
    results: tuple[ListCheckResult, ...],
) -> list[dict[str, object]]:
    return [
        {
            "name": result.name,
            "url": result.url,
            "status_code": result.status_code,
            "item_count": result.item_count,
            "minimum_count": result.minimum_count,
        }
        for result in results
    ]


if __name__ == "__main__":
    raise SystemExit(main())
