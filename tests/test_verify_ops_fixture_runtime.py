from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "verify_ops_fixture_runtime.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_ops_fixture_runtime",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load script module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VerifyOpsFixtureRuntimeTests(unittest.TestCase):
    def test_build_list_checks_uses_fixture_counts_as_minimums(self) -> None:
        module = load_module()
        fixture = {
            "organizations": [{"company_id": "company-1", "name": "Ops Company A"}, {}, {}],
            "drivers": [{"driver_id": "driver-1", "name": "Ops Driver A1-01"}] + ([{}] * 17),
            "vehicles": [{"vehicle_id": "vehicle-1", "plate_number": "12가3401"}] + ([{}] * 21),
            "regions": [{"region_id": "region-1", "region_code": "ops-region-a-1", "name": "Ops Region A-1"}] + ([{}] * 4),
            "region_analytics": {
                "daily_statistics": [{}] * 5,
                "performance_summaries": [{}] * 5,
            },
            "personnel_documents": [{"personnel_document_id": "doc-1", "title": "Ops Driver A1-01 근로 계약서"}] + ([{}] * 30),
            "assignments": [{}] * 11,
            "dispatch": {"plans": [{}] * 7, "schedules": [], "assignments": []},
            "delivery_records": {"records": [{}] * 25, "snapshots": []},
            "settlements": {"runs": [{}] * 5, "items": []},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            fixture_path = Path(tmp_dir) / "fixture.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

            checks = module.build_list_checks(fixture_path)

        expected = {
            "companies": 3,
            "drivers": 18,
            "vehicles": 22,
            "announcements": 2,
            "support_tickets": 2,
            "general_notifications": 2,
            "regions": 5,
            "region_daily_statistics": 5,
            "region_performance_summaries": 5,
            "personnel_documents": 31,
            "assignments": 11,
            "dispatch_plans": 7,
            "delivery_records": 25,
            "settlement_runs": 5,
        }
        self.assertEqual({check.name: check.minimum_count for check in checks}, expected)

    def test_build_detail_checks_uses_first_fixture_records(self) -> None:
        module = load_module()
        fixture = {
            "organizations": [{
                "company_id": "company-1",
                "name": "Ops Company A",
                "fleets": [{"fleet_id": "fleet-1", "name": "Ops Fleet A-1"}],
            }],
            "drivers": [{"driver_id": "driver-1", "fleet_id": "fleet-1", "name": "Ops Driver A1-01"}],
            "vehicles": [{"vehicle_id": "vehicle-1", "plate_number": "12가3401"}],
            "regions": [{"region_id": "region-1", "region_code": "ops-region-a-1", "name": "Ops Region A-1"}],
            "region_analytics": {"daily_statistics": [], "performance_summaries": []},
            "personnel_documents": [{"personnel_document_id": "doc-1", "title": "Ops Driver A1-01 근로 계약서"}],
            "assignments": [{
                "driver_id": "driver-1",
                "vehicle_id": "vehicle-1",
                "driver_vehicle_assignment_id": "assignment-1",
            }],
            "dispatch": {
                "plans": [{"dispatch_plan_id": "plan-1", "fleet_id": "fleet-1", "dispatch_date": "2026-03-30"}],
                "schedules": [{"vehicle_schedule_id": "schedule-1"}],
                "assignments": [{"dispatch_assignment_id": "dispatch-assignment-1"}],
            },
            "delivery_records": {
                "records": [],
                "snapshots": [{"daily_delivery_input_snapshot_id": "snapshot-1"}],
            },
            "settlements": {"runs": [], "items": []},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            fixture_path = Path(tmp_dir) / "fixture.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

            checks = module.build_detail_checks(fixture_path)

        self.assertEqual(
            [(check.name, check.path, check.expected_snippet) for check in checks],
            [
                ("company_detail", "/api/org/companies/company-1/", "Ops Company A"),
                ("fleet_detail", "/api/org/fleets/fleet-1/", "Ops Fleet A-1"),
                ("driver_detail", "/api/drivers/driver-1/", "Ops Driver A1-01"),
                ("vehicle_detail", "/api/vehicles/vehicle-masters/vehicle-1/", "12가3401"),
                ("region_detail", "/api/regions/region-1/", "Ops Region A-1"),
                ("personnel_document_detail", "/api/personnel-documents/documents/doc-1/", "Ops Driver A1-01 근로 계약서"),
                ("assignment_detail", "/api/driver-vehicle-assignments/assignments/assignment-1/", "assignment-1"),
                ("dispatch_plan_detail", "/api/dispatch/plans/plan-1/", "plan-1"),
                ("vehicle_schedule_detail", "/api/dispatch/vehicle-schedules/schedule-1/", "schedule-1"),
                ("dispatch_assignment_detail", "/api/dispatch/assignments/dispatch-assignment-1/", "dispatch-assignment-1"),
                ("daily_snapshot_detail", "/api/delivery-record/daily-snapshots/snapshot-1/", "snapshot-1"),
            ],
        )

    def test_build_seeded_detail_checks_uses_deterministic_seed_identifiers(self) -> None:
        module = load_module()

        checks = module.build_seeded_detail_checks()

        self.assertEqual(
            [(check.name, check.path, check.expected_snippet) for check in checks],
            [
                (
                    "announcement_detail",
                    "/api/announcements/92000000-0000-0000-0000-000000000001/",
                    "Policy Update For Operators",
                ),
                (
                    "support_ticket_detail",
                    "/api/ticket/tickets/93000000-0000-0000-0000-000000000001/",
                    "Driver App Inquiry",
                ),
                (
                    "general_notification_detail",
                    "/api/notifications/general/94000000-0000-0000-0000-000000000101/",
                    "Operator Policy Updated",
                ),
            ],
        )

    def test_run_list_checks_logs_in_and_verifies_minimum_counts(self) -> None:
        module = load_module()
        fixture = {
            "organizations": [{"company_id": "company-1", "name": "Ops Company A"}, {}, {}],
            "drivers": [{"driver_id": "driver-1", "name": "Ops Driver A1-01"}] + ([{}] * 17),
            "vehicles": [{"vehicle_id": "vehicle-1", "plate_number": "12가3401"}] + ([{}] * 21),
            "regions": [{"region_id": "region-1", "region_code": "ops-region-a-1", "name": "Ops Region A-1"}] + ([{}] * 4),
            "region_analytics": {
                "daily_statistics": [{}] * 5,
                "performance_summaries": [{}] * 5,
            },
            "personnel_documents": [{"personnel_document_id": "doc-1", "title": "Ops Driver A1-01 근로 계약서"}] + ([{}] * 30),
            "assignments": [{}] * 11,
            "dispatch": {"plans": [{}] * 7, "schedules": [], "assignments": []},
            "delivery_records": {"records": [{}] * 25, "snapshots": []},
            "settlements": {"runs": [{}] * 5, "items": []},
        }
        calls: list[tuple[str, str, dict[str, str] | None]] = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            fixture_path = Path(tmp_dir) / "fixture.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

            def fake_fetch(url: str, method: str, *, headers=None, body_bytes=None):
                calls.append((method, url, headers))
                path = url.removeprefix("http://localhost:8080")
                if path == "/api/auth/identity-login/":
                    payload = json.loads(body_bytes.decode("utf-8"))
                    self.assertEqual(payload["email"], "seed-admin@example.com")
                    self.assertEqual(payload["password"], "imjing12!")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps({"access_token": "token-123"}),
                    )
                expected_token_headers = {"Authorization": "Bearer token-123"}
                self.assertEqual(headers, expected_token_headers)
                responses = {
                    "/api/org/companies/": {"results": [{}, {}, {}, {}]},
                    "/api/drivers/": {"results": [{}] * 19},
                    "/api/vehicles/vehicle-masters/": {"results": [{}] * 23},
                    "/api/announcements/": {"results": [{}] * 2},
                    "/api/ticket/tickets/": {"results": [{}] * 2},
                    "/api/notifications/general/": {"results": [{}] * 2},
                    "/api/regions/": {"results": [{}] * 5},
                    "/api/region-analytics/daily-statistics/": {"results": [{}] * 5},
                    "/api/region-analytics/performance-summaries/": {"results": [{}] * 5},
                    "/api/personnel-documents/documents/": {"results": [{}] * 31},
                    "/api/driver-vehicle-assignments/assignments/": {"results": [{}] * 12},
                    "/api/dispatch/plans/": {"results": [{}] * 8},
                    "/api/delivery-record/records/": {"results": [{}] * 26},
                    "/api/settlements/runs/": {"results": [{}] * 6},
                }
                if path not in responses:
                    raise AssertionError(f"unexpected url: {url}")
                return module.FetchResult(
                    status_code=200,
                    body_text=json.dumps(responses[path]),
                )

            results = module.run_list_checks(
                base_url="http://localhost:8080",
                email="seed-admin@example.com",
                password="imjing12!",
                fixture_path=fixture_path,
                fetch=fake_fetch,
            )

        self.assertEqual(len(results), 14)
        self.assertEqual(calls[0][0:2], ("POST", "http://localhost:8080/api/auth/identity-login/"))
        self.assertEqual(calls[-1][0:2], ("GET", "http://localhost:8080/api/settlements/runs/"))

    def test_run_detail_checks_verifies_expected_detail_snippets(self) -> None:
        module = load_module()
        fixture = {
            "organizations": [{
                "company_id": "company-1",
                "name": "Ops Company A",
                "fleets": [{"fleet_id": "fleet-1", "name": "Ops Fleet A-1"}],
            }],
            "drivers": [{"driver_id": "driver-1", "name": "Ops Driver A1-01"}],
            "vehicles": [{"vehicle_id": "vehicle-1", "plate_number": "12가3401"}],
            "regions": [{"region_id": "region-1", "region_code": "ops-region-a-1", "name": "Ops Region A-1"}],
            "region_analytics": {"daily_statistics": [], "performance_summaries": []},
            "personnel_documents": [{"personnel_document_id": "doc-1", "title": "Ops Driver A1-01 근로 계약서"}],
            "assignments": [{
                "driver_id": "driver-1",
                "vehicle_id": "vehicle-1",
                "driver_vehicle_assignment_id": "assignment-1",
            }],
            "dispatch": {
                "plans": [{"dispatch_plan_id": "plan-1"}],
                "schedules": [{"vehicle_schedule_id": "schedule-1"}],
                "assignments": [{"dispatch_assignment_id": "dispatch-assignment-1"}],
            },
            "delivery_records": {
                "records": [],
                "snapshots": [{"daily_delivery_input_snapshot_id": "snapshot-1"}],
            },
            "settlements": {"runs": [], "items": []},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            fixture_path = Path(tmp_dir) / "fixture.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

            def fake_fetch(url: str, method: str, *, headers=None, body_bytes=None):
                self.assertEqual(method, "GET")
                self.assertEqual(headers, {"Authorization": "Bearer token-123"})
                snippets = {
                    "/api/org/companies/company-1/": "Ops Company A",
                    "/api/org/fleets/fleet-1/": "Ops Fleet A-1",
                    "/api/drivers/driver-1/": "Ops Driver A1-01",
                    "/api/vehicles/vehicle-masters/vehicle-1/": "12가3401",
                    "/api/regions/region-1/": "Ops Region A-1",
                    "/api/personnel-documents/documents/doc-1/": "Ops Driver A1-01 근로 계약서",
                    "/api/driver-vehicle-assignments/assignments/assignment-1/": "assignment-1",
                    "/api/dispatch/plans/plan-1/": "plan-1",
                    "/api/dispatch/vehicle-schedules/schedule-1/": "schedule-1",
                    "/api/dispatch/assignments/dispatch-assignment-1/": "dispatch-assignment-1",
                    "/api/delivery-record/daily-snapshots/snapshot-1/": "snapshot-1",
                }
                path = url.removeprefix("http://localhost:8080")
                return module.FetchResult(
                    status_code=200,
                    body_text=json.dumps({"text": snippets[path]}, ensure_ascii=False),
                )

            results = module.run_detail_checks(
                base_url="http://localhost:8080",
                token="token-123",
                checks=module.build_detail_checks(fixture_path),
                fetch=fake_fetch,
            )

        self.assertEqual(len(results), 11)

    def test_run_detail_checks_verifies_seeded_communication_details(self) -> None:
        module = load_module()

        def fake_fetch(url: str, method: str, *, headers=None, body_bytes=None):
            self.assertEqual(method, "GET")
            self.assertEqual(headers, {"Authorization": "Bearer token-123"})
            snippets = {
                "/api/announcements/92000000-0000-0000-0000-000000000001/": "Policy Update For Operators",
                "/api/ticket/tickets/93000000-0000-0000-0000-000000000001/": "Driver App Inquiry",
                "/api/notifications/general/94000000-0000-0000-0000-000000000101/": "Operator Policy Updated",
            }
            path = url.removeprefix("http://localhost:8080")
            return module.FetchResult(status_code=200, body_text=json.dumps({"text": snippets[path]}, ensure_ascii=False))

        results = module.run_detail_checks(
            base_url="http://localhost:8080",
            token="token-123",
            checks=module.build_seeded_detail_checks(),
            fetch=fake_fetch,
        )

        self.assertEqual(len(results), 3)

    def test_run_read_model_checks_verifies_dispatch_and_settlement_read_models(self) -> None:
        module = load_module()
        fixture = {
            "organizations": [{"company_id": "company-1", "name": "Ops Company A"}],
            "drivers": [{"driver_id": "driver-1", "fleet_id": "fleet-1", "name": "Ops Driver A1-01"}],
            "vehicles": [{"vehicle_id": "vehicle-1", "fleet_id": "fleet-1", "plate_number": "12가3401"}],
            "regions": [{"region_id": "region-1", "region_code": "ops-region-a-1", "name": "Ops Region A-1"}],
            "region_analytics": {"daily_statistics": [], "performance_summaries": []},
            "personnel_documents": [{"personnel_document_id": "doc-1", "title": "Ops Driver A1-01 근로 계약서"}],
            "assignments": [{"driver_id": "driver-1", "vehicle_id": "vehicle-1"}],
            "dispatch": {
                "plans": [{"fleet_id": "fleet-1", "dispatch_date": "2026-03-30"}],
                "schedules": [],
                "assignments": [],
            },
            "delivery_records": {"records": [], "snapshots": []},
            "settlements": {"runs": [{"settlement_run_id": "run-1"}], "items": [{"settlement_item_id": "item-1"}]},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            fixture_path = Path(tmp_dir) / "fixture.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

            def fake_fetch(url: str, method: str, *, headers=None, body_bytes=None):
                self.assertEqual(method, "GET")
                self.assertEqual(headers, {"Authorization": "Bearer token-123"})
                path = url.removeprefix("http://localhost:8080")
                responses = {
                    "/api/driver-ops/drivers/driver-1/": {
                        "driver_id": "driver-1",
                        "driver_name": "Ops Driver A1-01",
                    },
                    "/api/vehicle-ops/vehicles/vehicle-1/": {
                        "vehicle_id": "vehicle-1",
                        "plate_number": "12가3401",
                    },
                    "/api/dispatch-ops/summary/?dispatch_date=2026-03-30&fleet_id=fleet-1": {
                        "dispatch_date": "2026-03-30",
                        "fleet_id": "fleet-1",
                        "planned_volume": 120,
                        "planned_assignment_count": 12,
                        "matched_count": 10,
                    },
                    "/api/dispatch-ops/board/?dispatch_date=2026-03-30&fleet_id=fleet-1": [
                        {"plate_number": "12가3401", "planned_driver_name": "Ops Driver A1-01"}
                    ],
                    "/api/settlement-ops/drivers/driver-1/latest-settlement/": {
                        "driver_id": "driver-1",
                        "latest_settlement": {"settlement_run_id": "run-1"},
                    },
                    "/api/settlement-ops/runs/": [
                        {"settlement_run_id": "run-1"}
                    ],
                    "/api/settlement-ops/runs/run-1/": {
                        "settlement_run_id": "run-1"
                    },
                    "/api/settlement-ops/items/": [
                        {"settlement_item_id": "item-1"}
                    ],
                    "/api/settlement-ops/items/item-1/": {
                        "settlement_item_id": "item-1"
                    },
                }
                if path not in responses:
                    raise AssertionError(f"unexpected url: {url}")
                return module.FetchResult(status_code=200, body_text=json.dumps(responses[path], ensure_ascii=False))

            results = module.run_read_model_checks(
                base_url="http://localhost:8080",
                token="token-123",
                fixture_path=fixture_path,
                fetch=fake_fetch,
            )

        self.assertEqual([result.name for result in results], [
            "driver_ops_detail",
            "vehicle_ops_detail",
            "dispatch_ops_summary",
            "dispatch_ops_board",
            "settlement_ops_driver_latest",
            "settlement_ops_run_detail",
            "settlement_ops_item_detail",
        ])

    def test_run_auth_management_checks_verifies_self_service_and_manager_endpoints(self) -> None:
        module = load_module()

        def fake_fetch(url: str, method: str, *, headers=None, body_bytes=None):
            self.assertEqual(method, "GET")
            self.assertEqual(headers, {"Authorization": "Bearer token-123"})
            path = url.removeprefix("http://localhost:8080")
            responses = {
                "/api/auth/identity-me/": {
                    "session_kind": "normal",
                    "identity": {"identity_id": "identity-1", "name": "Admin Seed"},
                    "active_account": {"account_type": "system_admin", "account_id": "account-1"},
                },
                "/api/auth/identity-profile/": {
                    "identity_id": "identity-1",
                    "name": "Admin Seed",
                    "birth_date": "1990-01-01",
                },
                "/api/auth/identity-login-methods/": {
                    "methods": [{"identity_login_method_id": "method-1"}],
                },
                "/api/auth/identity-signup-requests/me/": {
                    "requests": [],
                    "inquiry_message": "none",
                },
                "/api/auth/identity-signup-requests/manage/?status=pending": {
                    "requests": [],
                },
                "/api/auth/manager-accounts/manage/": {
                    "accounts": [],
                },
            }
            if path not in responses:
                raise AssertionError(f"unexpected url: {url}")
            return module.FetchResult(
                status_code=200,
                body_text=json.dumps(responses[path], ensure_ascii=False),
            )

        results = module.run_auth_management_checks(
            base_url="http://localhost:8080",
            token="token-123",
            fetch=fake_fetch,
        )

        self.assertEqual(
            [result.name for result in results],
            [
                "identity_me",
                "identity_profile",
                "identity_login_methods",
                "identity_requests_me",
                "identity_requests_manage",
                "manager_accounts_manage",
            ],
        )

    def test_run_write_checks_cover_dispatch_and_settlement_create_and_patch_flow(self) -> None:
        module = load_module()
        calls: list[tuple[str, str, dict[str, str] | None, dict[str, object] | None]] = []
        fixture = {
            "organizations": [{
                "company_id": "company-1",
                "name": "Ops Company A",
                "fleets": [{"fleet_id": "fleet-1", "name": "Ops Fleet A-1"}],
            }],
            "drivers": [{"driver_id": "driver-1", "fleet_id": "fleet-1", "name": "Ops Driver A1-01"}],
            "vehicles": [],
            "regions": [],
            "region_analytics": {"daily_statistics": [], "performance_summaries": []},
            "personnel_documents": [],
            "assignments": [],
            "dispatch": {
                "plans": [{"dispatch_plan_id": "plan-1", "fleet_id": "fleet-1", "dispatch_date": "2026-03-31"}],
                "schedules": [],
                "assignments": [],
            },
            "delivery_records": {"records": [], "snapshots": []},
            "settlements": {"runs": [], "items": []},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            fixture_path = Path(tmp_dir) / "fixture.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

            def fake_fetch(url: str, method: str, *, headers=None, body_bytes=None):
                payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else None
                calls.append((method, url, headers, payload))
                path = url.removeprefix("http://localhost:8080")
                if path == "/api/announcements/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertTrue(str(payload["slug"]).startswith("ops-smoke-announcement-"))
                    self.assertEqual(payload["status"], "draft")
                    self.assertEqual(payload["exposure_scope"], "all")
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "announcement_id": "announcement-write-1",
                                "title": payload["title"],
                                "slug": payload["slug"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/announcements/announcement-write-1/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["status"], "archived")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "announcement_id": "announcement-write-1",
                                "status": "archived",
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/ticket/ticket-responses/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["ticket_id"], module.OPEN_SUPPORT_TICKET_ID)
                    self.assertIn("ops smoke support reply", payload["body"])
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "response_id": "support-response-1",
                                "ticket_id": payload["ticket_id"],
                                "body": payload["body"],
                                "author_role": "system_admin",
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == f"/api/ticket/tickets/{module.OPEN_SUPPORT_TICKET_ID}/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["status"], "in_progress")
                    self.assertEqual(payload["priority"], "high")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "ticket_id": module.OPEN_SUPPORT_TICKET_ID,
                                "status": "in_progress",
                                "priority": "high",
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/dispatch/outsourced-drivers/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["dispatch_plan_id"], "plan-1")
                    self.assertTrue(str(payload["name"]).startswith("Ops Smoke Outsourced"))
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "outsourced_driver_id": "outsourced-1",
                                "dispatch_plan_id": payload["dispatch_plan_id"],
                                "name": payload["name"],
                                "contact_number": payload["contact_number"],
                                "vehicle_note": payload["vehicle_note"],
                                "memo": payload["memo"],
                                "status": "active",
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/auth/identity-me/":
                    self.assertEqual(method, "GET")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123"})
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "session_kind": "normal",
                                "identity": {"identity_id": "identity-1"},
                                "active_account": {
                                    "account_type": "manager",
                                    "account_id": "manager-account-1",
                                },
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/notifications/general/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["recipient_account_id"], "manager-account-1")
                    self.assertEqual(payload["category"], "announcement")
                    self.assertEqual(payload["status"], "unread")
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "notification_id": "notification-write-1",
                                "recipient_account_id": payload["recipient_account_id"],
                                "category": payload["category"],
                                "source_type": payload["source_type"],
                                "source_ref": payload["source_ref"],
                                "title": payload["title"],
                                "body": payload["body"],
                                "status": payload["status"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/notifications/general/notification-write-1/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["status"], "read")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "notification_id": "notification-write-1",
                                "status": "read",
                                "read_at": "2026-04-06T09:00:00Z",
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/dispatch/outsourced-drivers/outsourced-1/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["memo"], "patched outsourced memo")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "outsourced_driver_id": "outsourced-1",
                                "memo": payload["memo"],
                                "status": "active",
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/dispatch/outsourced-drivers/outsourced-1/archive/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertIsNone(payload)
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "outsourced_driver_id": "outsourced-1",
                                "status": "archived",
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/delivery-record/daily-snapshots/bootstrap-from-dispatch/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["company_id"], "company-1")
                    self.assertEqual(payload["fleet_id"], "fleet-1")
                    self.assertEqual(payload["service_date"], "2026-03-31")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "created_count": 1,
                                "skipped_count": 0,
                                "created_snapshot_ids": ["snapshot-1"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/settlements/runs/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["company_id"], "company-1")
                    self.assertEqual(payload["fleet_id"], "fleet-1")
                    self.assertEqual(payload["status"], "draft")
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "settlement_run_id": "run-1",
                                "company_id": payload["company_id"],
                                "fleet_id": payload["fleet_id"],
                                "status": payload["status"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/settlements/items/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["settlement_run_id"], "run-1")
                    self.assertEqual(payload["driver_id"], "driver-1")
                    self.assertEqual(payload["payout_status"], "pending")
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "settlement_item_id": "item-1",
                                "settlement_run_id": payload["settlement_run_id"],
                                "driver_id": payload["driver_id"],
                                "amount": payload["amount"],
                                "payout_status": payload["payout_status"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/settlements/runs/run-1/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["status"], "reviewed")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "settlement_run_id": "run-1",
                                "status": "reviewed",
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/settlements/items/item-1/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["payout_status"], "paid")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "settlement_item_id": "item-1",
                                "payout_status": "paid",
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/personnel-documents/documents/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["driver_id"], "driver-1")
                    self.assertEqual(payload["document_type"], "contract")
                    self.assertEqual(payload["status"], "draft")
                    self.assertTrue(str(payload["title"]).startswith("Ops Smoke Document "))
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "personnel_document_id": "doc-write-1",
                                "driver_id": payload["driver_id"],
                                "document_type": payload["document_type"],
                                "status": payload["status"],
                                "title": payload["title"],
                                "document_number": payload["document_number"],
                                "issuer_name": payload["issuer_name"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/personnel-documents/documents/doc-write-1/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["status"], "active")
                    self.assertEqual(payload["notes"], "patched personnel document note")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "personnel_document_id": "doc-write-1",
                                "status": "active",
                                "notes": "patched personnel document note",
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/regions/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertTrue(str(payload["region_code"]).startswith("ops-smoke-region-"))
                    self.assertEqual(payload["status"], "draft")
                    self.assertEqual(payload["difficulty_level"], "medium")
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "region_id": "region-write-1",
                                "region_code": payload["region_code"],
                                "name": payload["name"],
                                "status": payload["status"],
                                "difficulty_level": payload["difficulty_level"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/regions/region-write-1/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["status"], "active")
                    self.assertEqual(payload["display_order"], 77)
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "region_id": "region-write-1",
                                "status": "active",
                                "display_order": 77,
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/org/companies/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertTrue(str(payload["name"]).startswith("Ops Smoke Company "))
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "company_id": "company-write-1",
                                "route_no": "C-9001",
                                "name": payload["name"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/org/fleets/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["company_id"], "company-write-1")
                    self.assertTrue(str(payload["name"]).startswith("Ops Smoke Fleet "))
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "fleet_id": "fleet-write-1",
                                "route_no": "F-9001",
                                "company_id": payload["company_id"],
                                "name": payload["name"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/org/companies/C-9001/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["name"], "Ops Smoke Company Updated")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "company_id": "company-write-1",
                                "route_no": "C-9001",
                                "name": payload["name"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/org/fleets/F-9001/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["name"], "Ops Smoke Fleet Updated")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "fleet_id": "fleet-write-1",
                                "route_no": "F-9001",
                                "company_id": "company-write-1",
                                "name": payload["name"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/drivers/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["company_id"], "company-1")
                    self.assertEqual(payload["fleet_id"], "fleet-1")
                    self.assertTrue(str(payload["name"]).startswith("Ops Smoke Driver "))
                    self.assertEqual(payload["employment_status"], "active")
                    self.assertEqual(payload["qualification_status"], "qualified")
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "driver_id": "driver-write-1",
                                "route_no": 9001,
                                "company_id": payload["company_id"],
                                "fleet_id": payload["fleet_id"],
                                "name": payload["name"],
                                "ev_id": payload["ev_id"],
                                "phone_number": payload["phone_number"],
                                "address": payload["address"],
                                "employment_status": payload["employment_status"],
                                "qualification_status": payload["qualification_status"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/drivers/9001/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["phone_number"], "010-8888-7777")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "driver_id": "driver-write-1",
                                "route_no": 9001,
                                "phone_number": payload["phone_number"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/vehicles/vehicle-masters/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["manufacturer_company_id"], "company-1")
                    self.assertTrue(str(payload["plate_number"]).startswith("90가"))
                    self.assertEqual(payload["vehicle_status"], "active")
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "vehicle_id": "vehicle-write-1",
                                "route_no": 9002,
                                "manufacturer_company_id": payload["manufacturer_company_id"],
                                "plate_number": payload["plate_number"],
                                "vin": payload["vin"],
                                "manufacturer_vehicle_code": payload["manufacturer_vehicle_code"],
                                "model_name": payload["model_name"],
                                "vehicle_status": payload["vehicle_status"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/vehicles/vehicle-masters/9002/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["model_name"], "Ops Smoke Cargo Van Updated")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "vehicle_id": "vehicle-write-1",
                                "route_no": 9002,
                                "model_name": payload["model_name"],
                                "vehicle_status": "active",
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/vehicles/vehicle-operator-accesses/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["vehicle_id"], "vehicle-write-1")
                    self.assertEqual(payload["operator_company_id"], "company-1")
                    self.assertEqual(payload["access_status"], "active")
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "vehicle_operator_access_id": "access-write-1",
                                "vehicle_id": payload["vehicle_id"],
                                "operator_company_id": payload["operator_company_id"],
                                "access_status": payload["access_status"],
                                "started_at": payload["started_at"],
                                "ended_at": payload["ended_at"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/driver-vehicle-assignments/assignments/":
                    self.assertEqual(method, "POST")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["driver_id"], "driver-write-1")
                    self.assertEqual(payload["vehicle_id"], "vehicle-write-1")
                    self.assertEqual(payload["operator_company_id"], "company-1")
                    self.assertEqual(payload["assignment_status"], "assigned")
                    return module.FetchResult(
                        status_code=201,
                        body_text=json.dumps(
                            {
                                "driver_vehicle_assignment_id": "assignment-write-1",
                                "route_no": 9003,
                                "driver_id": payload["driver_id"],
                                "vehicle_id": payload["vehicle_id"],
                                "operator_company_id": payload["operator_company_id"],
                                "assignment_status": payload["assignment_status"],
                                "assigned_at": payload["assigned_at"],
                                "unassigned_at": None,
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/driver-vehicle-assignments/assignments/9003/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["assignment_status"], "unassigned")
                    self.assertEqual(payload["unassigned_at"], "2026-04-06T09:30:00Z")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "driver_vehicle_assignment_id": "assignment-write-1",
                                "route_no": 9003,
                                "assignment_status": payload["assignment_status"],
                                "unassigned_at": payload["unassigned_at"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                if path == "/api/vehicles/vehicle-operator-accesses/access-write-1/":
                    self.assertEqual(method, "PATCH")
                    self.assertEqual(headers, {"Authorization": "Bearer token-123", "Content-Type": "application/json"})
                    self.assertEqual(payload["access_status"], "suspended")
                    self.assertEqual(payload["ended_at"], "2026-04-06T10:00:00Z")
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps(
                            {
                                "vehicle_operator_access_id": "access-write-1",
                                "access_status": payload["access_status"],
                                "ended_at": payload["ended_at"],
                            },
                            ensure_ascii=False,
                        ),
                    )
                raise AssertionError(f"unexpected url: {url}")

            results = module.run_write_checks(
                base_url="http://localhost:8080",
                token="token-123",
                fixture_path=fixture_path,
                fetch=fake_fetch,
            )

        self.assertEqual(
            [result.name for result in results],
            [
                "announcement_create",
                "announcement_patch",
                "support_reply_create",
                "support_ticket_patch",
                "general_notification_create",
                "general_notification_patch",
                "outsourced_driver_create",
                "outsourced_driver_patch",
                "dispatch_snapshot_bootstrap",
                "outsourced_driver_archive",
                "settlement_run_create",
                "settlement_item_create",
                "settlement_run_patch",
                "settlement_item_patch",
                "personnel_document_create",
                "personnel_document_patch",
                "region_create",
                "region_patch",
                "company_create",
                "fleet_create",
                "company_patch",
                "fleet_patch",
                "driver_create",
                "driver_patch",
                "vehicle_create",
                "vehicle_patch",
                "vehicle_operator_access_create",
                "assignment_create",
                "assignment_patch",
                "vehicle_operator_access_patch",
            ],
        )
        self.assertEqual(
            [call[1] for call in calls],
            [
                "http://localhost:8080/api/announcements/",
                "http://localhost:8080/api/announcements/announcement-write-1/",
                "http://localhost:8080/api/ticket/ticket-responses/",
                f"http://localhost:8080/api/ticket/tickets/{module.OPEN_SUPPORT_TICKET_ID}/",
                "http://localhost:8080/api/auth/identity-me/",
                "http://localhost:8080/api/notifications/general/",
                "http://localhost:8080/api/notifications/general/notification-write-1/",
                "http://localhost:8080/api/dispatch/outsourced-drivers/",
                "http://localhost:8080/api/dispatch/outsourced-drivers/outsourced-1/",
                "http://localhost:8080/api/delivery-record/daily-snapshots/bootstrap-from-dispatch/",
                "http://localhost:8080/api/dispatch/outsourced-drivers/outsourced-1/archive/",
                "http://localhost:8080/api/settlements/runs/",
                "http://localhost:8080/api/settlements/items/",
                "http://localhost:8080/api/settlements/runs/run-1/",
                "http://localhost:8080/api/settlements/items/item-1/",
                "http://localhost:8080/api/personnel-documents/documents/",
                "http://localhost:8080/api/personnel-documents/documents/doc-write-1/",
                "http://localhost:8080/api/regions/",
                "http://localhost:8080/api/regions/region-write-1/",
                "http://localhost:8080/api/org/companies/",
                "http://localhost:8080/api/org/fleets/",
                "http://localhost:8080/api/org/companies/C-9001/",
                "http://localhost:8080/api/org/fleets/F-9001/",
                "http://localhost:8080/api/drivers/",
                "http://localhost:8080/api/drivers/9001/",
                "http://localhost:8080/api/vehicles/vehicle-masters/",
                "http://localhost:8080/api/vehicles/vehicle-masters/9002/",
                "http://localhost:8080/api/vehicles/vehicle-operator-accesses/",
                "http://localhost:8080/api/driver-vehicle-assignments/assignments/",
                "http://localhost:8080/api/driver-vehicle-assignments/assignments/9003/",
                "http://localhost:8080/api/vehicles/vehicle-operator-accesses/access-write-1/",
            ],
        )

    def test_run_list_checks_rejects_when_count_is_below_fixture_minimum(self) -> None:
        module = load_module()
        fixture = {
            "organizations": [{}, {}, {}],
            "drivers": [{}] * 18,
            "vehicles": [{}] * 22,
            "regions": [{}] * 5,
            "region_analytics": {
                "daily_statistics": [{}] * 5,
                "performance_summaries": [{}] * 5,
            },
            "personnel_documents": [{}] * 31,
            "assignments": [{}] * 11,
            "dispatch": {"plans": [{}] * 7, "schedules": [], "assignments": []},
            "delivery_records": {"records": [{}] * 25, "snapshots": []},
            "settlements": {"runs": [{}] * 5, "items": []},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            fixture_path = Path(tmp_dir) / "fixture.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

            def fake_fetch(url: str, method: str, *, headers=None, body_bytes=None):
                path = url.removeprefix("http://localhost:8080")
                if path == "/api/auth/identity-login/":
                    return module.FetchResult(
                        status_code=200,
                        body_text=json.dumps({"access_token": "token-123"}),
                    )
                return module.FetchResult(
                    status_code=200,
                    body_text=json.dumps({"results": []}),
                )

            with self.assertRaises(module.RuntimeVerificationError) as ctx:
                module.run_list_checks(
                    base_url="http://localhost:8080",
                    email="seed-admin@example.com",
                    password="imjing12!",
                    fixture_path=fixture_path,
                    fetch=fake_fetch,
                )

        self.assertIn("companies", str(ctx.exception))
        self.assertIn("expected at least 3", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
