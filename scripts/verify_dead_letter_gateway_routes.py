#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from typing import Callable
import urllib.error
from urllib.parse import urlsplit
import urllib.request


DEFAULT_BASE_URL = "http://localhost:8080"
DEFAULT_DETAIL_ID = "00000000-0000-0000-0000-000000000000"


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


@dataclass(frozen=True)
class RouteCheck:
    name: str
    method: str
    path: str
    expected_status: int
    expected_location: str | None = None


@dataclass(frozen=True)
class FetchResult:
    status_code: int
    location: str | None = None
    body_text: str | None = None


@dataclass(frozen=True)
class RouteResult:
    name: str
    method: str
    url: str
    status_code: int
    location: str | None = None


class RouteVerificationError(RuntimeError):
    pass


Fetch = Callable[[str, str], FetchResult]


def build_route_checks(detail_id: str = DEFAULT_DETAIL_ID) -> tuple[RouteCheck, ...]:
    return (
        RouteCheck(
            name="dead-letter list no-slash redirect",
            method="GET",
            path="/api/telemetry-dead-letters",
            expected_status=301,
            expected_location="/api/telemetry-dead-letters/",
        ),
        RouteCheck(
            name="dead-letter health no-slash redirect",
            method="GET",
            path="/api/telemetry-dead-letters/health",
            expected_status=301,
            expected_location="/api/telemetry-dead-letters/health/",
        ),
        RouteCheck(
            name="dead-letter health route",
            method="GET",
            path="/api/telemetry-dead-letters/health/",
            expected_status=200,
        ),
        RouteCheck(
            name="dead-letter list route auth gate",
            method="GET",
            path="/api/telemetry-dead-letters/",
            expected_status=401,
        ),
        RouteCheck(
            name="dead-letter detail no-slash redirect",
            method="GET",
            path=f"/api/telemetry-dead-letters/{detail_id}",
            expected_status=301,
            expected_location=f"/api/telemetry-dead-letters/{detail_id}/",
        ),
        RouteCheck(
            name="dead-letter detail route auth gate",
            method="GET",
            path=f"/api/telemetry-dead-letters/{detail_id}/",
            expected_status=401,
        ),
        RouteCheck(
            name="dead-letter ingest without trailing slash",
            method="POST",
            path="/api/telemetry-dead-letters/ingest",
            expected_status=404,
        ),
        RouteCheck(
            name="dead-letter ingest with trailing slash",
            method="POST",
            path="/api/telemetry-dead-letters/ingest/",
            expected_status=404,
        ),
    )


def build_fetch(timeout: float = 10.0) -> Fetch:
    opener = urllib.request.build_opener(NoRedirectHandler())

    def fetch(url: str, method: str) -> FetchResult:
        body = b"{}" if method == "POST" else None
        headers = {"Content-Type": "application/json"} if method == "POST" else {}
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with opener.open(request, timeout=timeout) as response:
                return FetchResult(
                    status_code=response.getcode(),
                    location=response.headers.get("Location"),
                    body_text=response.read().decode("utf-8", errors="replace"),
                )
        except urllib.error.HTTPError as exc:
            return FetchResult(
                status_code=exc.code,
                location=exc.headers.get("Location"),
                body_text=exc.read().decode("utf-8", errors="replace"),
            )

    return fetch


def run_route_checks(
    base_url: str,
    fetch: Fetch,
    detail_id: str = DEFAULT_DETAIL_ID,
) -> tuple[RouteResult, ...]:
    normalized_base_url = base_url.rstrip("/")
    results: list[RouteResult] = []
    for check in build_route_checks(detail_id=detail_id):
        url = f"{normalized_base_url}{check.path}"
        result = fetch(url, check.method)
        if result.status_code != check.expected_status:
            raise RouteVerificationError(
                f"{check.name}: expected {check.expected_status}, got {result.status_code}"
            )
        if (
            check.expected_location is not None
            and _normalize_location(result.location) != check.expected_location
        ):
            raise RouteVerificationError(
                f"{check.name}: expected Location {check.expected_location!r}, got {result.location!r}"
            )
        results.append(
            RouteResult(
                name=check.name,
                method=check.method,
                url=url,
                status_code=result.status_code,
                location=result.location,
            )
        )
    return tuple(results)


def _normalize_location(location: str | None) -> str | None:
    if location is None:
        return None
    parts = urlsplit(location)
    if parts.scheme or parts.netloc:
        return parts.path or "/"
    return location


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify dead-letter gateway route exposure against a live stack.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--detail-id", default=DEFAULT_DETAIL_ID)
    args = parser.parse_args()

    results = run_route_checks(
        base_url=args.base_url,
        detail_id=args.detail_id,
        fetch=build_fetch(),
    )
    print(
        json.dumps(
            [
                {
                    "name": result.name,
                    "method": result.method,
                    "url": result.url,
                    "status_code": result.status_code,
                    "location": result.location,
                }
                for result in results
            ],
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
