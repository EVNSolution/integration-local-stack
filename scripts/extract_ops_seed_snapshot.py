#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import subprocess
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ops-derived-sample.json"
)
DEFAULT_KEY_PATH = Path(
    "/Users/jiin/Documents/Files/02_EVnSolution/00_Source_code/CLEVER/"
    "clever-analytics-pipeline/keys/dev-analytics-keypair.pem"
)
DEFAULT_EC2_HOST = "3.39.216.177"
DEFAULT_EC2_USER = "ec2-user"
DEFAULT_REMOTE_DIR = "~/dev-analytics"
COMPANY_LIMIT = 3
FLEET_LIMIT = 6
DRIVER_CAP = 12
VEHICLE_CAP = 8
DISPATCH_UNIT_CAP = 8

FLEET_SUMMARY_SQL = """
with fleet_driver as (
  select fleet_id, count(distinct driver_id) as driver_count
  from public.documents_dailysettlement
  where work_date >= current_date - interval '30 days'
  group by fleet_id
),
fleet_delivery as (
  select fleet_id,
         count(*) as delivery_log_count,
         coalesce(sum(total_box), 0) as box_sum,
         coalesce(sum(total_house), 0) as house_sum
  from public.documents_evdeliverylog
  where delivery_date >= current_date - interval '30 days'
  group by fleet_id
),
fleet_schedule as (
  select fleet_id,
         count(*) as schedule_count,
         count(distinct vehicle_id) as scheduled_vehicle_count
  from public.schedule_vehicleschedule
  group by fleet_id
),
fleet_match as (
  select fleet_id,
         count(*) as match_count,
         count(distinct vehicle_id) as matched_vehicle_count
  from public.schedule_drivervehiclematch
  group by fleet_id
)
select
  c.id as source_company_id,
  c.name as source_company_name,
  f.id as source_fleet_id,
  f.name as source_fleet_name,
  coalesce(fd.driver_count, 0) as recent_driver_count,
  coalesce(fl.delivery_log_count, 0) as recent_delivery_log_count,
  coalesce(fl.box_sum, 0) as recent_box_sum,
  coalesce(fl.house_sum, 0) as recent_house_sum,
  coalesce(fs.schedule_count, 0) as lifetime_schedule_count,
  coalesce(fs.scheduled_vehicle_count, 0) as lifetime_scheduled_vehicle_count,
  coalesce(fm.match_count, 0) as lifetime_match_count,
  coalesce(fm.matched_vehicle_count, 0) as lifetime_matched_vehicle_count
from public.core_fleet f
join public.core_client c on c.id = f.client_id
left join fleet_driver fd on fd.fleet_id = f.id
left join fleet_delivery fl on fl.fleet_id = f.id
left join fleet_schedule fs on fs.fleet_id = f.id
left join fleet_match fm on fm.fleet_id = f.id
where coalesce(f.is_active, true) = true
  and (
    coalesce(fd.driver_count, 0) > 0
    or coalesce(fl.delivery_log_count, 0) > 0
    or coalesce(fs.schedule_count, 0) > 0
    or coalesce(fm.match_count, 0) > 0
  )
order by recent_delivery_log_count desc, recent_driver_count desc, lifetime_match_count desc, source_fleet_id
limit 20;
"""


DAILY_METRICS_SQL_TEMPLATE = """
select
  work_date::text as work_date,
  fleet_id as source_fleet_id,
  count(distinct driver_id) as drivers,
  count(*) as settlement_rows,
  coalesce(sum(box_count), 0) as box_sum,
  coalesce(sum(house_count), 0) as house_sum,
  coalesce(sum(settlement_amount), 0) as settlement_sum
from public.documents_dailysettlement
where work_date >= current_date - interval '14 days'
  and fleet_id in ({fleet_ids})
group by work_date, fleet_id
order by work_date desc, settlement_rows desc;
"""


def _run_remote_csv_query(
    sql: str,
    *,
    key_path: Path,
    ec2_host: str,
    ec2_user: str,
    remote_dir: str,
) -> list[dict[str, str]]:
    remote_script = f"""cd {remote_dir}
set -a && source .env && set +a
PGPASSWORD="$PROD_DB_PASS" psql -h "$PROD_DB_HOST" -p "$PROD_DB_PORT" -U "$PROD_DB_USER" -d "$PROD_DB_NAME" --csv <<'SQL'
{sql}
SQL
"""
    result = subprocess.run(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            str(key_path),
            f"{ec2_user}@{ec2_host}",
            remote_script,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return list(csv.DictReader(io.StringIO(result.stdout)))


def _to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(float(value))


def _to_amount(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(round(float(value)))


def _scaled_count(raw: int, *, max_raw: int, cap: int, fallback: int = 1) -> int:
    if raw <= 0:
        return fallback
    if max_raw <= 0:
        return min(cap, max(fallback, raw))
    scaled = round(raw / max_raw * cap)
    return max(fallback, min(cap, scaled))


def _synthetic_company_name(index: int) -> str:
    return f"Ops Company {chr(64 + index)}"


def _synthetic_fleet_name(company_index: int, fleet_index: int) -> str:
    return f"Ops Fleet {chr(64 + company_index)}-{fleet_index}"


def _synthetic_driver_name(company_index: int, fleet_index: int, driver_index: int) -> str:
    return f"Ops Driver {chr(64 + company_index)}{fleet_index:01d}-{driver_index:02d}"


def _synthetic_plate(index: int) -> str:
    return f"12가{3400 + index:04d}"


def _stable_uuid(kind: str, source_key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ops-derived-fixture:{kind}:{source_key}"))


def _synthetic_region_name(company_index: int, fleet_index: int) -> str:
    return f"Ops Region {chr(64 + company_index)}-{fleet_index}"


def _synthetic_region_code(company_index: int, fleet_index: int) -> str:
    return f"ops-region-{chr(96 + company_index)}-{fleet_index}"


def _synthetic_polygon(seed_index: int) -> dict[str, Any]:
    base_lng = 126.90 + seed_index * 0.03
    base_lat = 37.45 + seed_index * 0.02
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [round(base_lng, 6), round(base_lat, 6)],
                [round(base_lng + 0.015, 6), round(base_lat, 6)],
                [round(base_lng + 0.015, 6), round(base_lat + 0.012, 6)],
                [round(base_lng, 6), round(base_lat + 0.012, 6)],
                [round(base_lng, 6), round(base_lat, 6)],
            ]
        ],
    }


def _build_daily_index(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["source_fleet_id"]].append(row)
    return grouped


def build_fixture(
    fleet_rows: list[dict[str, str]],
    daily_rows: list[dict[str, str]],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    selected_fleets = fleet_rows[:FLEET_LIMIT]
    daily_index = _build_daily_index(daily_rows)

    max_driver_raw = max((_to_int(row["recent_driver_count"]) for row in selected_fleets), default=0)
    max_vehicle_raw = max(
        (
            max(
                _to_int(row["lifetime_scheduled_vehicle_count"]),
                _to_int(row["lifetime_matched_vehicle_count"]),
            )
            for row in selected_fleets
        ),
        default=0,
    )

    fixture: dict[str, Any] = {
        "source_summary": {
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "fleet_count": len(selected_fleets),
            "company_count": 0,
            "source_fleets": [],
        },
        "organizations": [],
        "drivers": [],
        "vehicles": [],
        "assignments": [],
        "dispatch": {"plans": [], "schedules": [], "assignments": []},
        "delivery_records": {"records": [], "snapshots": []},
        "settlements": {"runs": [], "items": []},
        "regions": [],
        "region_analytics": {"daily_statistics": [], "performance_summaries": []},
        "personnel_documents": [],
    }

    companies: dict[str, dict[str, Any]] = {}
    company_order: list[str] = []
    plate_index = 0

    for fleet_row in selected_fleets:
        source_company_id = fleet_row["source_company_id"]
        if source_company_id not in companies and len(companies) < COMPANY_LIMIT:
            company_index = len(companies) + 1
            company = {
                "company_id": _stable_uuid("company", source_company_id),
                "source_key": source_company_id,
                "name": _synthetic_company_name(company_index),
                "fleets": [],
            }
            companies[source_company_id] = company
            company_order.append(source_company_id)
        if source_company_id not in companies:
            continue

        company_index = company_order.index(source_company_id) + 1
        fleet_index = len(companies[source_company_id]["fleets"]) + 1
        fleet_source_key = fleet_row["source_fleet_id"]
        fleet_id = _stable_uuid("fleet", fleet_source_key)
        driver_raw = _to_int(fleet_row["recent_driver_count"])
        delivery_log_raw = _to_int(fleet_row["recent_delivery_log_count"])
        vehicle_raw = max(
            _to_int(fleet_row["lifetime_scheduled_vehicle_count"]),
            _to_int(fleet_row["lifetime_matched_vehicle_count"]),
        )
        driver_count = (
            _scaled_count(driver_raw, max_raw=max_driver_raw, cap=DRIVER_CAP, fallback=1)
            if driver_raw > 0
            else min(3, max(1, delivery_log_raw))
        )
        vehicle_count = (
            _scaled_count(vehicle_raw, max_raw=max_vehicle_raw, cap=VEHICLE_CAP, fallback=1)
            if vehicle_raw > 0
            else max(1, min(VEHICLE_CAP, math.ceil(driver_count * 0.6)))
        )
        dispatch_unit_count = max(1, min(DISPATCH_UNIT_CAP, min(driver_count, vehicle_count)))

        companies[source_company_id]["fleets"].append(
            {
                "fleet_id": fleet_id,
                "source_key": fleet_source_key,
                "name": _synthetic_fleet_name(company_index, fleet_index),
            }
        )
        fixture["source_summary"]["source_fleets"].append(
            {
                "source_company_id": source_company_id,
                "source_fleet_id": fleet_source_key,
                "recent_driver_count": driver_raw,
                "recent_delivery_log_count": delivery_log_raw,
                "recent_box_sum": _to_int(fleet_row["recent_box_sum"]),
                "recent_house_sum": _to_int(fleet_row["recent_house_sum"]),
                "lifetime_vehicle_count": vehicle_raw,
                "local_driver_count": driver_count,
                "local_vehicle_count": vehicle_count,
            }
        )

        drivers_for_fleet: list[dict[str, Any]] = []
        for driver_index in range(1, driver_count + 1):
            driver_id = _stable_uuid("driver", f"{fleet_source_key}:{driver_index}")
            driver_payload = {
                "driver_id": driver_id,
                "company_id": companies[source_company_id]["company_id"],
                "fleet_id": fleet_id,
                "name": _synthetic_driver_name(company_index, fleet_index, driver_index),
                "ev_id": f"OPS-{company_index}{fleet_index:01d}-{driver_index:03d}",
                "phone_number": f"010-9000-{company_index}{fleet_index:01d}{driver_index:02d}"[-13:],
                "address": f"Ops District {company_index}-{fleet_index}",
                "employment_status": "active",
                "qualification_status": "qualified",
            }
            fixture["drivers"].append(driver_payload)
            drivers_for_fleet.append(driver_payload)

        vehicles_for_fleet: list[dict[str, Any]] = []
        for vehicle_index in range(1, vehicle_count + 1):
            plate_index += 1
            vehicle_id = _stable_uuid("vehicle", f"{fleet_source_key}:{vehicle_index}")
            vehicle_payload = {
                "vehicle_id": vehicle_id,
                "manufacturer_company_id": companies[source_company_id]["company_id"],
                "operator_company_id": companies[source_company_id]["company_id"],
                "plate_number": _synthetic_plate(plate_index),
                "vin": f"OPSVIN{company_index:02d}{fleet_index:02d}{vehicle_index:04d}",
                "manufacturer_vehicle_code": f"OPS-MODEL-{company_index:02d}{fleet_index:02d}",
                "model_name": "Ops Cargo Van",
                "vehicle_status": "active",
                "started_at": datetime.combine(today - timedelta(days=90), datetime.min.time()).isoformat() + "Z",
            }
            fixture["vehicles"].append(vehicle_payload)
            vehicles_for_fleet.append(vehicle_payload)

        for pair_index in range(dispatch_unit_count):
            assignment_id = _stable_uuid("assignment", f"{fleet_source_key}:{pair_index + 1}")
            fixture["assignments"].append(
                {
                    "driver_vehicle_assignment_id": assignment_id,
                    "driver_id": drivers_for_fleet[pair_index]["driver_id"],
                    "vehicle_id": vehicles_for_fleet[pair_index]["vehicle_id"],
                    "operator_company_id": companies[source_company_id]["company_id"],
                    "assignment_status": "assigned",
                    "assigned_at": datetime.combine(today - timedelta(days=30), datetime.min.time()).isoformat() + "Z",
                }
            )

        fleet_daily_rows = daily_index.get(fleet_source_key, [])[:3]
        if not fleet_daily_rows:
            fleet_daily_rows = [
                {
                    "work_date": (today - timedelta(days=1)).isoformat(),
                    "source_fleet_id": fleet_source_key,
                    "drivers": str(driver_raw or driver_count),
                    "settlement_rows": str(driver_raw or driver_count),
                    "box_sum": fleet_row["recent_box_sum"] or str(driver_count * 12),
                    "house_sum": fleet_row["recent_house_sum"] or str(driver_count * 6),
                    "settlement_sum": str(max(driver_count, 1) * 125000),
                }
            ]

        fleet_settlement_total = 0
        latest_dispatch_date = None
        for daily_index_offset, daily_row in enumerate(fleet_daily_rows, start=1):
            service_date = date.fromisoformat(daily_row["work_date"])
            latest_dispatch_date = latest_dispatch_date or service_date
            raw_driver_basis = max(_to_int(daily_row["drivers"]), 1)
            box_sum = max(_to_int(daily_row["box_sum"]), dispatch_unit_count * 8)
            house_sum = max(_to_int(daily_row["house_sum"]), dispatch_unit_count * 4)
            settlement_sum = max(_to_amount(daily_row["settlement_sum"]), dispatch_unit_count * 100000)
            planned_volume = max(dispatch_unit_count * 8, round(box_sum * dispatch_unit_count / raw_driver_basis))

            plan_id = _stable_uuid("dispatch-plan", f"{fleet_source_key}:{service_date.isoformat()}")
            fixture["dispatch"]["plans"].append(
                {
                    "dispatch_plan_id": plan_id,
                    "company_id": companies[source_company_id]["company_id"],
                    "fleet_id": fleet_id,
                    "dispatch_date": service_date.isoformat(),
                    "planned_volume": planned_volume,
                    "dispatch_status": "published",
                }
            )

            for pair_index in range(dispatch_unit_count):
                vehicle_payload = vehicles_for_fleet[pair_index % len(vehicles_for_fleet)]
                driver_payload = drivers_for_fleet[pair_index % len(drivers_for_fleet)]
                schedule_id = _stable_uuid(
                    "vehicle-schedule",
                    f"{fleet_source_key}:{service_date.isoformat()}:{pair_index + 1}",
                )
                dispatch_assignment_id = _stable_uuid(
                    "dispatch-assignment",
                    f"{fleet_source_key}:{service_date.isoformat()}:{pair_index + 1}",
                )
                delivery_count = max(1, round(box_sum / dispatch_unit_count))
                base_amount = round(settlement_sum / dispatch_unit_count)
                distance_km = round(12.5 + pair_index * 1.75, 2)
                source_reference = f"ops-fixture-{fleet_index}-{daily_index_offset}-{pair_index + 1}"

                fixture["dispatch"]["schedules"].append(
                    {
                        "vehicle_schedule_id": schedule_id,
                        "vehicle_id": vehicle_payload["vehicle_id"],
                        "fleet_id": fleet_id,
                        "dispatch_date": service_date.isoformat(),
                        "shift_slot": "A",
                        "schedule_status": "planned",
                        "starts_at": "08:00:00",
                        "ends_at": "18:00:00",
                    }
                )
                fixture["dispatch"]["assignments"].append(
                    {
                        "dispatch_assignment_id": dispatch_assignment_id,
                        "vehicle_schedule_id": schedule_id,
                        "vehicle_id": vehicle_payload["vehicle_id"],
                        "driver_id": driver_payload["driver_id"],
                        "operator_company_id": companies[source_company_id]["company_id"],
                        "dispatch_date": service_date.isoformat(),
                        "shift_slot": "A",
                        "assignment_status": "assigned",
                        "assigned_at": datetime.combine(service_date, datetime.min.time()).replace(hour=8).isoformat() + "Z",
                    }
                )
                record_id = _stable_uuid(
                    "delivery-record",
                    f"{fleet_source_key}:{service_date.isoformat()}:{driver_payload['driver_id']}",
                )
                snapshot_id = _stable_uuid(
                    "delivery-snapshot",
                    f"{fleet_source_key}:{service_date.isoformat()}:{driver_payload['driver_id']}",
                )
                fixture["delivery_records"]["records"].append(
                    {
                        "delivery_record_id": record_id,
                        "company_id": companies[source_company_id]["company_id"],
                        "fleet_id": fleet_id,
                        "driver_id": driver_payload["driver_id"],
                        "service_date": service_date.isoformat(),
                        "source_reference": source_reference,
                        "delivery_count": delivery_count,
                        "distance_km": f"{distance_km:.2f}",
                        "base_amount": f"{base_amount:.2f}",
                        "status": "confirmed",
                        "payload": {
                            "source": "ops-derived-fixture",
                            "boxes": delivery_count,
                            "houses": max(1, round(house_sum / dispatch_unit_count)),
                        },
                    }
                )
                fixture["delivery_records"]["snapshots"].append(
                    {
                        "daily_delivery_input_snapshot_id": snapshot_id,
                        "company_id": companies[source_company_id]["company_id"],
                        "fleet_id": fleet_id,
                        "driver_id": driver_payload["driver_id"],
                        "service_date": service_date.isoformat(),
                        "delivery_count": delivery_count,
                        "total_distance_km": f"{distance_km:.2f}",
                        "total_base_amount": f"{base_amount:.2f}",
                        "source_record_count": 1,
                        "status": "active",
                    }
                )
                fleet_settlement_total += base_amount

        run_id = _stable_uuid("settlement-run", fleet_source_key)
        fixture["settlements"]["runs"].append(
            {
                "settlement_run_id": run_id,
                "company_id": companies[source_company_id]["company_id"],
                "fleet_id": fleet_id,
                "period_start": (today.replace(day=1)).isoformat(),
                "period_end": today.isoformat(),
                "status": "calculated",
            }
        )
        item_amount = max(50000, round(fleet_settlement_total / max(1, len(drivers_for_fleet))))
        for driver_payload in drivers_for_fleet:
            fixture["settlements"]["items"].append(
                {
                    "settlement_item_id": _stable_uuid(
                        "settlement-item", f"{fleet_source_key}:{driver_payload['driver_id']}"
                    ),
                    "settlement_run_id": run_id,
                    "driver_id": driver_payload["driver_id"],
                    "amount": f"{item_amount:.2f}",
                    "payout_status": "pending",
                }
            )

    fixture["organizations"] = [companies[key] for key in company_order]
    fixture["source_summary"]["company_count"] = len(fixture["organizations"])
    _append_region_fixture(fixture)
    _append_personnel_documents(fixture, today=today)
    return fixture


def _append_region_fixture(fixture: dict[str, Any]) -> None:
    difficulty_levels = ("low", "medium", "high")
    fleet_regions: list[dict[str, Any]] = []
    fleet_region_by_fleet_id: dict[str, dict[str, Any]] = {}

    for company_index, company in enumerate(fixture["organizations"], start=1):
        for fleet_index, fleet in enumerate(company.get("fleets", []), start=1):
            region_id = _stable_uuid("region", fleet["fleet_id"])
            region_payload = {
                "region_id": region_id,
                "region_code": _synthetic_region_code(company_index, fleet_index),
                "name": _synthetic_region_name(company_index, fleet_index),
                "status": "active",
                "difficulty_level": difficulty_levels[(company_index + fleet_index - 2) % len(difficulty_levels)],
                "polygon_geojson": _synthetic_polygon(len(fleet_regions) + 1),
                "description": f"{company['name']} / {fleet['name']} 운영 권역",
                "display_order": len(fleet_regions) + 1,
            }
            fleet_regions.append(region_payload)
            fleet_region_by_fleet_id[fleet["fleet_id"]] = region_payload

    fixture["regions"] = fleet_regions

    stats_by_region_id: dict[str, dict[str, Any]] = {}
    for record in fixture["delivery_records"]["records"]:
        region_payload = fleet_region_by_fleet_id.get(record["fleet_id"])
        if region_payload is None:
            continue
        key = f"{region_payload['region_id']}:{record['service_date']}"
        entry = stats_by_region_id.setdefault(
            key,
            {
                "region_daily_statistic_id": _stable_uuid("region-daily", key),
                "region_id": region_payload["region_id"],
                "region_code_snapshot": region_payload["region_code"],
                "service_date": record["service_date"],
                "delivery_count": 0,
                "completed_delivery_count": 0,
                "exception_delivery_count": 0,
                "total_distance_km": 0.0,
                "total_base_amount": 0.0,
                "average_delivery_minutes": 0.0,
                "_row_count": 0,
            },
        )
        delivery_count = int(record["delivery_count"])
        exception_count = 1 if delivery_count >= 14 else 0
        completed_count = max(delivery_count - exception_count, 0)
        entry["delivery_count"] += delivery_count
        entry["completed_delivery_count"] += completed_count
        entry["exception_delivery_count"] += exception_count
        entry["total_distance_km"] += float(record["distance_km"])
        entry["total_base_amount"] += float(record["base_amount"])
        entry["average_delivery_minutes"] += 18 + (entry["_row_count"] * 1.5)
        entry["_row_count"] += 1

    daily_statistics: list[dict[str, Any]] = []
    performance_summaries: list[dict[str, Any]] = []
    grouped_stats_by_region: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in stats_by_region_id.values():
        row_count = max(entry.pop("_row_count"), 1)
        entry["total_distance_km"] = f"{entry['total_distance_km']:.2f}"
        entry["total_base_amount"] = f"{entry['total_base_amount']:.2f}"
        entry["average_delivery_minutes"] = f"{entry['average_delivery_minutes'] / row_count:.2f}"
        daily_statistics.append(entry)
        grouped_stats_by_region[entry["region_id"]].append(entry)

    for region_payload in fleet_regions:
        region_stats = sorted(
            grouped_stats_by_region.get(region_payload["region_id"], []),
            key=lambda item: item["service_date"],
        )
        if not region_stats:
            continue
        total_delivery = sum(item["delivery_count"] for item in region_stats)
        total_completed = sum(item["completed_delivery_count"] for item in region_stats)
        total_amount = sum(float(item["total_base_amount"]) for item in region_stats)
        completion_rate = (total_completed / total_delivery * 100) if total_delivery else 0
        performance_summaries.append(
            {
                "region_performance_summary_id": _stable_uuid(
                    "region-performance",
                    f"{region_payload['region_id']}:{region_stats[0]['service_date']}:{region_stats[-1]['service_date']}",
                ),
                "region_id": region_payload["region_id"],
                "region_code_snapshot": region_payload["region_code"],
                "difficulty_level_snapshot": region_payload["difficulty_level"],
                "period_start": region_stats[0]["service_date"],
                "period_end": region_stats[-1]["service_date"],
                "delivery_count": total_delivery,
                "completion_rate": f"{completion_rate:.2f}",
                "productivity_score": f"{(total_delivery / len(region_stats)) * 1.7:.2f}",
                "cost_per_delivery": f"{(total_amount / total_delivery) if total_delivery else 0:.2f}",
                "notes": f"{region_payload['name']} synthetic summary",
            }
        )

    fixture["region_analytics"] = {
        "daily_statistics": sorted(daily_statistics, key=lambda item: (item["service_date"], item["region_code_snapshot"])),
        "performance_summaries": sorted(
            performance_summaries,
            key=lambda item: (item["period_start"], item["region_code_snapshot"]),
        ),
    }


def _append_personnel_documents(fixture: dict[str, Any], *, today: date) -> None:
    documents: list[dict[str, Any]] = []
    for index, driver in enumerate(fixture["drivers"], start=1):
        company_tag = driver["name"].split()[2]
        contract_issued_on = today - timedelta(days=90 + index)
        contract_expires_on = contract_issued_on + timedelta(days=365)
        documents.append(
            {
                "personnel_document_id": _stable_uuid("personnel-document", f"{driver['driver_id']}:contract"),
                "driver_id": driver["driver_id"],
                "document_type": "contract",
                "status": "active",
                "title": f"{driver['name']} 근로 계약서",
                "document_number": f"OPS-CONTRACT-{company_tag.replace('-', '')}-{index:03d}",
                "issuer_name": "Ops HR",
                "issued_on": contract_issued_on.isoformat(),
                "expires_on": contract_expires_on.isoformat(),
                "notes": "Ops-derived fixture contract.",
                "external_reference": f"ops://personnel/contracts/{index:03d}",
                "payload": {"signed": True, "source": "ops-derived-fixture"},
            }
        )
        if index <= 8:
            license_issued_on = today - timedelta(days=30 + index)
            license_expires_on = license_issued_on + timedelta(days=180 if index % 3 else 20)
            status = "expired" if license_expires_on < today else "active"
            documents.append(
                {
                    "personnel_document_id": _stable_uuid(
                        "personnel-document", f"{driver['driver_id']}:license"
                    ),
                    "driver_id": driver["driver_id"],
                    "document_type": "license_or_certificate",
                    "status": status,
                    "title": f"{driver['name']} 운송 자격 증빙",
                    "document_number": f"OPS-LICENSE-{company_tag.replace('-', '')}-{index:03d}",
                    "issuer_name": "Ops Cert Center",
                    "issued_on": license_issued_on.isoformat(),
                    "expires_on": license_expires_on.isoformat(),
                    "notes": "Synthetic qualification certificate.",
                    "external_reference": f"ops://personnel/license/{index:03d}",
                    "payload": {"verified": status == "active", "source": "ops-derived-fixture"},
                }
            )
        if index <= 4:
            proof_issued_on = today - timedelta(days=20 + index)
            documents.append(
                {
                    "personnel_document_id": _stable_uuid(
                        "personnel-document", f"{driver['driver_id']}:bank"
                    ),
                    "driver_id": driver["driver_id"],
                    "document_type": "bank_account_proof",
                    "status": "active",
                    "title": f"{driver['name']} 계좌 증빙",
                    "document_number": f"OPS-BANK-{company_tag.replace('-', '')}-{index:03d}",
                    "issuer_name": "Ops Bank",
                    "issued_on": proof_issued_on.isoformat(),
                    "expires_on": None,
                    "notes": "Synthetic payout account proof.",
                    "external_reference": f"ops://personnel/bank/{index:03d}",
                    "payload": {"preferred": index % 2 == 0, "source": "ops-derived-fixture"},
                }
            )

    fixture["personnel_documents"] = documents


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract sanitized production-shaped fixture for local stack.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--key-path", type=Path, default=DEFAULT_KEY_PATH)
    parser.add_argument("--ec2-host", default=DEFAULT_EC2_HOST)
    parser.add_argument("--ec2-user", default=DEFAULT_EC2_USER)
    parser.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR)
    args = parser.parse_args()

    fleet_rows = _run_remote_csv_query(
        FLEET_SUMMARY_SQL,
        key_path=args.key_path,
        ec2_host=args.ec2_host,
        ec2_user=args.ec2_user,
        remote_dir=args.remote_dir,
    )
    selected_fleet_ids = [row["source_fleet_id"] for row in fleet_rows[:FLEET_LIMIT]]
    if not selected_fleet_ids:
        raise SystemExit("No active fleet rows could be extracted from production-shaped source.")
    fleet_id_sql = ", ".join(selected_fleet_ids)
    daily_rows = _run_remote_csv_query(
        DAILY_METRICS_SQL_TEMPLATE.format(fleet_ids=fleet_id_sql),
        key_path=args.key_path,
        ec2_host=args.ec2_host,
        ec2_user=args.ec2_user,
        remote_dir=args.remote_dir,
    )
    fixture = build_fixture(fleet_rows, daily_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote sanitized fixture to {args.output}")
    print(
        json.dumps(
            {
                "companies": len(fixture["organizations"]),
                "drivers": len(fixture["drivers"]),
                "vehicles": len(fixture["vehicles"]),
                "regions": len(fixture["regions"]),
                "personnel_documents": len(fixture["personnel_documents"]),
                "dispatch_plans": len(fixture["dispatch"]["plans"]),
                "delivery_records": len(fixture["delivery_records"]["records"]),
                "settlement_items": len(fixture["settlements"]["items"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
