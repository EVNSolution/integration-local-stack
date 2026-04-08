from datetime import date
from pathlib import Path
import importlib.util


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "extract_ops_seed_snapshot.py"
)
SPEC = importlib.util.spec_from_file_location("extract_ops_seed_snapshot", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_scaled_count_caps_and_preserves_positive_floor():
    assert MODULE._scaled_count(54, max_raw=54, cap=12, fallback=1) == 12
    assert MODULE._scaled_count(3, max_raw=54, cap=12, fallback=1) == 1
    assert MODULE._scaled_count(0, max_raw=54, cap=12, fallback=2) == 2


def test_build_fixture_generates_sanitized_local_bundle():
    fleet_rows = [
        {
            "source_company_id": "1",
            "source_company_name": "컬리",
            "source_fleet_id": "29",
            "source_fleet_name": "컬리/R",
            "recent_driver_count": "54",
            "recent_delivery_log_count": "1524",
            "recent_box_sum": "167072",
            "recent_house_sum": "78043",
            "lifetime_schedule_count": "5",
            "lifetime_scheduled_vehicle_count": "3",
            "lifetime_match_count": "126",
            "lifetime_matched_vehicle_count": "18",
        }
    ]
    daily_rows = [
        {
            "work_date": "2026-03-31",
            "source_fleet_id": "29",
            "drivers": "54",
            "settlement_rows": "60",
            "box_sum": "6791",
            "house_sum": "3282",
            "settlement_sum": "7186478",
        }
    ]

    fixture = MODULE.build_fixture(fleet_rows, daily_rows, today=date(2026, 4, 6))

    assert fixture["organizations"][0]["name"] == "Ops Company A"
    assert fixture["organizations"][0]["fleets"][0]["name"] == "Ops Fleet A-1"
    assert len(fixture["drivers"]) == 12
    assert len(fixture["vehicles"]) == 8
    assert fixture["drivers"][0]["name"].startswith("Ops Driver")
    assert fixture["vehicles"][0]["plate_number"].startswith("12가")
    assert fixture["regions"][0]["name"] == "Ops Region A-1"
    assert fixture["region_analytics"]["daily_statistics"][0]["region_code_snapshot"] == "ops-region-a-1"
    assert fixture["personnel_documents"][0]["title"].endswith("근로 계약서")
    assert fixture["dispatch"]["plans"][0]["dispatch_status"] == "published"
    assert fixture["delivery_records"]["records"][0]["payload"]["source"] == "ops-derived-fixture"
    assert fixture["settlements"]["runs"][0]["status"] == "calculated"
