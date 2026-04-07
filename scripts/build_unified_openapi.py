#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ast
import copy
import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


HTTP_METHODS = ("get", "post", "put", "patch", "delete")
GENERIC_METHODS = {
    "ListCreateAPIView": ["get", "post"],
    "RetrieveUpdateDestroyAPIView": ["get", "put", "patch", "delete"],
    "RetrieveUpdateAPIView": ["get", "put", "patch"],
    "CreateAPIView": ["post"],
    "ListAPIView": ["get"],
    "RetrieveAPIView": ["get"],
}
VIEWSET_METHODS = {
    "ModelViewSet": {
        "collection": ["get", "post"],
        "detail": ["get", "put", "patch", "delete"],
    },
    "ReadOnlyModelViewSet": {
        "collection": ["get"],
        "detail": ["get"],
    },
}
GROUP_ORDER = [
    "Registry",
    "Operations View",
    "Write Owner",
    "Edge And Access",
    "Telemetry And Support",
]
COMPONENT_SECTIONS = (
    "schemas",
    "responses",
    "parameters",
    "examples",
    "requestBodies",
    "headers",
    "securitySchemes",
    "links",
    "callbacks",
)

STACK_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = Path(__file__).resolve().parents[3]
INVENTORY_PATH = PLATFORM_ROOT / "docs" / "mappings" / "current-runtime-inventory.md"
RESPONSIBILITY_MATRIX_PATH = PLATFORM_ROOT / "docs" / "mappings" / "repo-responsibility-matrix.md"
OUTPUT_PATH = STACK_ROOT / "compose" / "api-docs" / "clever-unified.openapi.yaml"
SCHEMA_INPUT_DIR = STACK_ROOT / "compose" / "api-docs" / "service-schemas"
SCHEMA_ENABLED_SERVICES = {
    "service-account-access",
    "service-delivery-record",
    "service-driver-operations-view",
    "service-dispatch-operations-view",
    "service-dispatch-registry",
    "service-driver-profile",
    "service-organization-registry",
    "service-personnel-document-registry",
    "service-announcement-registry",
    "service-region-registry",
    "service-region-analytics",
    "service-notification-hub",
    "service-support-registry",
    "service-settlement-operations-view",
    "service-settlement-payroll",
    "service-settlement-registry",
    "service-terminal-registry",
    "service-telemetry-hub",
    "service-telemetry-dead-letter",
    "service-vehicle-assignment",
    "service-vehicle-operations-view",
    "service-vehicle-registry",
}


@dataclass
class ServiceMetadata:
    repo_name: str
    compose_service: str
    gateway_prefix: str
    status: str
    role_summary: str
    owns: str
    does_not_own: str
    depends_on: str
    repo_path: Path


@dataclass
class ViewClassInfo:
    name: str
    bases: list[str]
    http_methods: list[str] = field(default_factory=list)
    http_method_names: list[str] = field(default_factory=list)
    lookup_field: str | None = None
    permission_classes: list[str] = field(default_factory=list)
    authentication_classes: list[str] = field(default_factory=list)


@dataclass
class RouterRegistration:
    prefix: str
    view_class_name: str


@dataclass
class RouteDefinition:
    service: ServiceMetadata
    path: str
    methods: list[str]
    view_class_name: str
    urls_path: Path
    views_path: Path
    parameters: list[dict[str, Any]]


@dataclass
class SchemaBackedArtifact:
    paths: dict[str, dict[str, Any]]
    components: dict[str, dict[str, Any]]


def clean_cell(value: str) -> str:
    return value.strip().strip("`").strip()


def parse_markdown_row(line: str) -> list[str]:
    return [clean_cell(cell) for cell in line.strip().strip("|").split("|")]


def parse_table_after_heading(path: Path, heading: str) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    heading_index = None
    for idx, line in enumerate(lines):
        if line.strip() == heading:
            heading_index = idx
            break
    if heading_index is None:
        raise ValueError(f"Heading not found: {heading} in {path}")

    index = heading_index + 1
    while index < len(lines) and not lines[index].strip().startswith("|"):
        index += 1
    if index + 1 >= len(lines):
        raise ValueError(f"Markdown table not found after heading: {heading}")

    headers = parse_markdown_row(lines[index])
    index += 2

    rows: list[dict[str, str]] = []
    while index < len(lines) and lines[index].strip().startswith("|"):
        values = parse_markdown_row(lines[index])
        if len(values) == len(headers):
            rows.append(dict(zip(headers, values)))
        index += 1
    return rows


def load_active_services() -> list[ServiceMetadata]:
    inventory_rows = parse_table_after_heading(INVENTORY_PATH, "## Active Runtime Repos")
    matrix_rows = parse_table_after_heading(RESPONSIBILITY_MATRIX_PATH, "## Matrix")
    matrix_by_repo = {row["Target repo"]: row for row in matrix_rows}

    services: list[ServiceMetadata] = []
    for row in inventory_rows:
        repo_name = row["Target repo"]
        if not repo_name.startswith("service-"):
            continue
        if row["Status"] != "active runtime":
            continue
        if row["Gateway prefix"] == "internal-only":
            continue

        matrix_row = matrix_by_repo.get(repo_name)
        if matrix_row is None:
            raise ValueError(f"Responsibility matrix row missing for {repo_name}")

        services.append(
            ServiceMetadata(
                repo_name=repo_name,
                compose_service=row["Compose service"],
                gateway_prefix=row["Gateway prefix"],
                status=row["Status"],
                role_summary=row["Role summary"],
                owns=matrix_row["Owns"],
                does_not_own=matrix_row["Does not own"],
                depends_on=matrix_row["Depends on"],
                repo_path=PLATFORM_ROOT / "development" / repo_name,
            )
        )
    return services


def expression_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def parse_name_list(node: ast.AST) -> list[str]:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return []

    values: list[str] = []
    for element in node.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            values.append(element.value)
            continue

        name = expression_name(element)
        if name:
            values.append(name)
    return values


def parse_view_classes(views_path: Path) -> dict[str, ViewClassInfo]:
    module = ast.parse(views_path.read_text(encoding="utf-8"), filename=str(views_path))
    classes: dict[str, ViewClassInfo] = {}

    for node in module.body:
        if not isinstance(node, ast.ClassDef):
            continue

        info = ViewClassInfo(
            name=node.name,
            bases=[name for name in (expression_name(base) for base in node.bases) if name],
        )

        for child in node.body:
            if isinstance(child, ast.FunctionDef) and child.name.lower() in HTTP_METHODS:
                info.http_methods.append(child.name.lower())
                continue

            if not isinstance(child, ast.Assign):
                continue

            targets = [target.id for target in child.targets if isinstance(target, ast.Name)]
            if "http_method_names" in targets:
                info.http_method_names = [value.lower() for value in parse_name_list(child.value)]
            if "lookup_field" in targets and isinstance(child.value, ast.Constant) and isinstance(child.value.value, str):
                info.lookup_field = child.value.value
            if "permission_classes" in targets:
                info.permission_classes = parse_name_list(child.value)
            if "authentication_classes" in targets:
                info.authentication_classes = parse_name_list(child.value)

        classes[info.name] = info
    return classes


def router_detail_pattern(prefix: str, lookup_field: str | None) -> str:
    parameter_name = lookup_field or "id"
    converter = "uuid" if parameter_name.endswith("_id") else "str"
    return f"{prefix}/<{converter}:{parameter_name}>/"


def parse_router_registrations(module: ast.Module) -> dict[str, list[RouterRegistration]]:
    router_names: set[str] = set()
    registrations: dict[str, list[RouterRegistration]] = {}

    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if isinstance(node.value, ast.Call) and expression_name(node.value.func) in {"SimpleRouter", "DefaultRouter"}:
                    router_names.add(target.id)
                    registrations.setdefault(target.id, [])
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue

        call = node.value
        if not isinstance(call.func, ast.Attribute):
            continue
        if call.func.attr != "register":
            continue
        if not isinstance(call.func.value, ast.Name):
            continue
        if call.func.value.id not in router_names:
            continue
        if len(call.args) < 2:
            continue
        if not isinstance(call.args[0], ast.Constant) or not isinstance(call.args[0].value, str):
            continue

        view_class_name = expression_name(call.args[1])
        if not view_class_name:
            continue

        registrations[call.func.value.id].append(
            RouterRegistration(prefix=call.args[0].value, view_class_name=view_class_name)
        )

    return registrations


def infer_methods_from_view(info: ViewClassInfo) -> list[str]:
    methods = list(dict.fromkeys(info.http_methods))
    if not methods:
        for base in info.bases:
            if base in GENERIC_METHODS:
                methods = list(GENERIC_METHODS[base])
                break
    if info.http_method_names:
        methods = [method for method in methods if method in info.http_method_names]
    return methods


def infer_router_methods(info: ViewClassInfo, *, detail: bool) -> list[str]:
    methods: list[str] = []
    bucket = "detail" if detail else "collection"
    for base in info.bases:
        if base in VIEWSET_METHODS:
            methods = list(VIEWSET_METHODS[base][bucket])
            break
    if info.http_method_names:
        methods = [method for method in methods if method in info.http_method_names]
    return methods


def join_relative_path(base: str, suffix: str) -> str:
    if not base:
        return suffix
    if not base.endswith("/"):
        base = f"{base}/"
    return f"{base}{suffix}"


def join_gateway_path(gateway_prefix: str, local_path: str) -> str:
    prefix = gateway_prefix if gateway_prefix.startswith("/") else f"/{gateway_prefix}"
    if not prefix.endswith("/"):
        prefix = f"{prefix}/"

    combined = prefix if not local_path else f"{prefix}{local_path}"
    combined = re.sub(r"/{2,}", "/", combined)
    return combined if combined.startswith("/") else f"/{combined}"


def normalize_openapi_path(path: str) -> tuple[str, list[dict[str, Any]]]:
    parameters: list[dict[str, Any]] = []

    def replace_match(match: re.Match[str]) -> str:
        converter = match.group(1) or "str"
        name = match.group(2)
        schema: dict[str, Any] = {"type": "string"}
        if converter == "uuid" or name.endswith("_id"):
            schema["format"] = "uuid"
        parameters.append(
            {
                "name": name,
                "in": "path",
                "required": True,
                "schema": schema,
            }
        )
        return f"{{{name}}}"

    normalized = re.sub(r"<(?:(\w+):)?(\w+)>", replace_match, path)
    return normalized, parameters


def humanize_camel(text: str) -> str:
    text = re.sub(r"(ViewSet|APIView|View)$", "", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = text.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def singularize(word: str) -> str:
    if word.endswith("ies"):
        return f"{word[:-3]}y"
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def humanize_resource(prefix: str) -> str:
    return humanize_camel(prefix.replace("/", " ").replace("-", " "))


def build_router_summary(prefix: str, method: str, *, detail: bool) -> str:
    resource = humanize_resource(prefix)
    singular = singularize(resource)
    if not detail and method == "get":
        return f"List {resource}"
    if not detail and method == "post":
        return f"Create {singular}"
    if detail and method == "get":
        return f"Get {singular}"
    if detail and method == "put":
        return f"Update {singular}"
    if detail and method == "patch":
        return f"Patch {singular}"
    if detail and method == "delete":
        return f"Delete {singular}"
    return f"{method.upper()} {singular}"


def build_path_summary(info: ViewClassInfo, method: str) -> str:
    if info.name == "HealthView":
        return "Health Check"

    if info.name.endswith("ListCreateView"):
        resource = humanize_camel(info.name[: -len("ListCreateView")])
        if method == "get":
            return f"List {resource}"
        if method == "post":
            return f"Create {singularize(resource)}"

    if info.name.endswith("ListView") and method == "get":
        return f"List {humanize_camel(info.name[: -len('ListView')])}"

    if info.name.endswith("DetailView"):
        resource = humanize_camel(info.name[: -len("DetailView")])
        if method == "get":
            return f"Get {resource}"
        if method == "put":
            return f"Update {resource}"
        if method == "patch":
            return f"Patch {resource}"
        if method == "delete":
            return f"Delete {resource}"

    label = humanize_camel(info.name)
    if len(info.http_methods) <= 1:
        return label
    return f"{method.upper()} {label}"


def tag_group_for_service(repo_name: str) -> str:
    if repo_name == "service-account-access":
        return "Edge And Access"
    if repo_name.endswith("operations-view"):
        return "Operations View"
    if repo_name.startswith("service-telemetry-"):
        return "Telemetry And Support"
    if repo_name in {
        "service-delivery-record",
        "service-settlement-payroll",
        "service-dispatch-registry",
        "service-vehicle-assignment",
    }:
        return "Write Owner"
    return "Registry"


def relative_to_platform(path: Path) -> str:
    return str(path.relative_to(PLATFORM_ROOT))


def service_schema_path(service: ServiceMetadata) -> Path:
    return SCHEMA_INPUT_DIR / f"{service.repo_name}.openapi.yaml"


def namespaced_component_name(service: ServiceMetadata, component_name: str) -> str:
    return f"{service.repo_name}__{component_name}"


def rewrite_component_refs(service: ServiceMetadata, value: Any) -> Any:
    if isinstance(value, dict):
        return {key: rewrite_component_refs(service, child) for key, child in value.items()}
    if isinstance(value, list):
        return [rewrite_component_refs(service, item) for item in value]
    if not isinstance(value, str):
        return value

    match = re.fullmatch(r"#/components/([^/]+)/([^/]+)", value)
    if not match:
        return value

    section_name, component_name = match.groups()
    return f"#/components/{section_name}/{namespaced_component_name(service, component_name)}"


def load_schema_components(service: ServiceMetadata, exported_schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_components = exported_schema.get("components", {})
    if not isinstance(raw_components, dict):
        return {}

    rewritten_components: dict[str, dict[str, Any]] = {}
    for section_name in COMPONENT_SECTIONS:
        raw_bucket = raw_components.get(section_name)
        if not isinstance(raw_bucket, dict) or not raw_bucket:
            continue

        rewritten_components[section_name] = {
            namespaced_component_name(service, component_name): rewrite_component_refs(
                service,
                copy.deepcopy(component_value),
            )
            for component_name, component_value in raw_bucket.items()
        }
    return rewritten_components


def merge_components(
    target_components: dict[str, dict[str, Any]],
    source_components: dict[str, dict[str, Any]],
) -> None:
    for section_name, source_bucket in source_components.items():
        target_bucket = target_components.setdefault(section_name, {})
        for component_name, component_value in source_bucket.items():
            target_bucket[component_name] = component_value


def is_service_source_file(service_root: Path, path: Path) -> bool:
    relative_parts = path.relative_to(service_root).parts
    excluded_parts = {"site-packages", "__pycache__", "migrations", "tests"}
    for part in relative_parts:
        if part.startswith("."):
            return False
        if part in excluded_parts:
            return False
    return True


def route_description(route: RouteDefinition, info: ViewClassInfo) -> str:
    lines = [
        "Generated from current active MSA service route definitions.",
        f"Owner repo: `{route.service.repo_name}`",
        f"Compose service: `{route.service.compose_service}`",
        f"Gateway prefix: `{route.service.gateway_prefix}`",
        f"Route source: `{relative_to_platform(route.urls_path)}`",
        f"View source: `{relative_to_platform(route.views_path)}`",
        f"View class: `{route.view_class_name}`",
        f"Role summary: {route.service.role_summary}",
        f"Owns: {route.service.owns}",
        f"Does not own: {route.service.does_not_own}",
        f"Depends on: {route.service.depends_on}",
    ]

    if info.permission_classes:
        lines.append(f"Permission classes: {', '.join(info.permission_classes)}")
    if info.authentication_classes:
        lines.append(f"Authentication classes: {', '.join(info.authentication_classes)}")

    lines.append(
        "Schema note: request and response body schemas are not generated yet; this artifact currently documents the current MSA route inventory."
    )
    return "\n\n".join(lines)


def schema_operation_description(service: ServiceMetadata, operation: dict[str, Any]) -> str:
    existing_description = str(operation.get("description", "")).strip()
    metadata = [
        "Merged from service-owned OpenAPI export.",
        f"Owner repo: `{service.repo_name}`",
        f"Compose service: `{service.compose_service}`",
        f"Gateway prefix: `{service.gateway_prefix}`",
        f"Role summary: {service.role_summary}",
        f"Owns: {service.owns}",
        f"Does not own: {service.does_not_own}",
        f"Depends on: {service.depends_on}",
    ]
    return "\n\n".join(part for part in [existing_description, *metadata] if part)


def merge_parameters(*parameter_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    for parameter_list in parameter_lists:
        for parameter in parameter_list:
            if not isinstance(parameter, dict):
                continue
            key = (parameter.get("in"), parameter.get("name"))
            merged[key] = copy.deepcopy(parameter)
    return list(merged.values())


def maybe_prefix_service_path(service: ServiceMetadata, schema_path_value: str) -> str:
    if schema_path_value.startswith(service.gateway_prefix):
        return schema_path_value
    local_path = schema_path_value.lstrip("/")
    return join_gateway_path(service.gateway_prefix, local_path)


def load_schema_backed_paths(service: ServiceMetadata) -> SchemaBackedArtifact | None:
    schema_path = service_schema_path(service)
    if not schema_path.exists():
        return None

    exported_schema = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    exported_paths = exported_schema.get("paths", {})
    components = load_schema_components(service, exported_schema)
    loaded_paths: dict[str, dict[str, Any]] = {}

    for raw_path, raw_path_item in exported_paths.items():
        if not isinstance(raw_path_item, dict):
            continue

        raw_path_item = rewrite_component_refs(service, copy.deepcopy(raw_path_item))
        normalized_path, extra_path_parameters = normalize_openapi_path(
            maybe_prefix_service_path(service, raw_path)
        )
        path_level_parameters = raw_path_item.get("parameters", [])
        target_path_item: dict[str, Any] = {}

        for method, raw_operation in raw_path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            if not isinstance(raw_operation, dict):
                continue

            operation = copy.deepcopy(raw_operation)
            operation["tags"] = [service.repo_name]
            operation["description"] = schema_operation_description(service, operation)
            operation["x-clever-owner-repo"] = service.repo_name
            operation["x-clever-compose-service"] = service.compose_service
            operation["x-clever-gateway-prefix"] = service.gateway_prefix
            operation["x-clever-source-of-truth-doc"] = "docs/mappings/current-runtime-inventory.md"
            operation["x-clever-runtime-status"] = service.status
            operation["x-clever-schema-source"] = "service-owned-openapi"

            merged_parameters = merge_parameters(
                extra_path_parameters,
                path_level_parameters,
                operation.get("parameters", []),
            )
            if merged_parameters:
                operation["parameters"] = merged_parameters

            target_path_item[method] = operation

        if target_path_item:
            loaded_paths[normalized_path] = target_path_item

    return SchemaBackedArtifact(paths=loaded_paths, components=components)


def parse_leaf_routes(service: ServiceMetadata) -> list[RouteDefinition]:
    routes: list[RouteDefinition] = []
    leaf_urls_files = sorted(
        path
        for path in service.repo_path.rglob("urls.py")
        if path.parent.name != "config"
        and is_service_source_file(service.repo_path, path)
    )

    if not leaf_urls_files:
        raise ValueError(f"No leaf urls.py files found for {service.repo_name}")

    for urls_path in leaf_urls_files:
        views_path = urls_path.with_name("views.py")
        if not views_path.exists():
            raise ValueError(f"Missing views.py for {urls_path}")

        view_infos = parse_view_classes(views_path)
        module = ast.parse(urls_path.read_text(encoding="utf-8"), filename=str(urls_path))
        router_registrations = parse_router_registrations(module)

        for node in module.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == "urlpatterns" for target in node.targets):
                continue
            if not isinstance(node.value, (ast.List, ast.Tuple)):
                continue

            for pattern_node in node.value.elts:
                if not isinstance(pattern_node, ast.Call):
                    continue
                if expression_name(pattern_node.func) != "path":
                    continue
                if len(pattern_node.args) < 2:
                    continue
                if not isinstance(pattern_node.args[0], ast.Constant) or not isinstance(pattern_node.args[0].value, str):
                    continue

                local_path = pattern_node.args[0].value
                target_node = pattern_node.args[1]

                if isinstance(target_node, ast.Call) and expression_name(target_node.func) == "include":
                    include_target = target_node.args[0] if target_node.args else None
                    if not isinstance(include_target, ast.Attribute) or include_target.attr != "urls":
                        continue
                    if not isinstance(include_target.value, ast.Name):
                        continue

                    for registration in router_registrations.get(include_target.value.id, []):
                        info = view_infos.get(registration.view_class_name)
                        if info is None:
                            raise ValueError(f"View class {registration.view_class_name} missing in {views_path}")

                        collection_local = join_relative_path(local_path, f"{registration.prefix}/")
                        collection_path, collection_params = normalize_openapi_path(
                            join_gateway_path(service.gateway_prefix, collection_local)
                        )
                        collection_methods = infer_router_methods(info, detail=False)
                        if collection_methods:
                            routes.append(
                                RouteDefinition(
                                    service=service,
                                    path=collection_path,
                                    methods=collection_methods,
                                    view_class_name=registration.view_class_name,
                                    urls_path=urls_path,
                                    views_path=views_path,
                                    parameters=collection_params,
                                )
                            )

                        detail_local = join_relative_path(
                            local_path,
                            router_detail_pattern(registration.prefix, info.lookup_field),
                        )
                        detail_path, detail_params = normalize_openapi_path(
                            join_gateway_path(service.gateway_prefix, detail_local)
                        )
                        detail_methods = infer_router_methods(info, detail=True)
                        if detail_methods:
                            routes.append(
                                RouteDefinition(
                                    service=service,
                                    path=detail_path,
                                    methods=detail_methods,
                                    view_class_name=registration.view_class_name,
                                    urls_path=urls_path,
                                    views_path=views_path,
                                    parameters=detail_params,
                                )
                            )
                    continue

                if not isinstance(target_node, ast.Call):
                    continue
                if not isinstance(target_node.func, ast.Attribute) or target_node.func.attr != "as_view":
                    continue

                view_class_name = expression_name(target_node.func.value)
                if not view_class_name:
                    continue

                info = view_infos.get(view_class_name)
                if info is None:
                    raise ValueError(f"View class {view_class_name} missing in {views_path}")

                methods = infer_methods_from_view(info)
                if not methods:
                    continue

                full_path, parameters = normalize_openapi_path(
                    join_gateway_path(service.gateway_prefix, local_path)
                )
                routes.append(
                    RouteDefinition(
                        service=service,
                        path=full_path,
                        methods=methods,
                        view_class_name=view_class_name,
                        urls_path=urls_path,
                        views_path=views_path,
                        parameters=parameters,
                    )
                )

    return routes


def build_tag(service: ServiceMetadata) -> dict[str, Any]:
    description = "\n\n".join(
        [
            service.role_summary,
            f"Gateway prefix: `{service.gateway_prefix}`",
            f"Compose service: `{service.compose_service}`",
            f"Owns: {service.owns}",
            f"Does not own: {service.does_not_own}",
            f"Depends on: {service.depends_on}",
        ]
    )
    return {
        "name": service.repo_name,
        "description": description,
        "x-clever-owner-repo": service.repo_name,
        "x-clever-compose-service": service.compose_service,
        "x-clever-gateway-prefix": service.gateway_prefix,
        "x-clever-source-of-truth-doc": "docs/mappings/current-runtime-inventory.md",
        "x-clever-runtime-status": service.status,
    }


def info_description(service_count: int, path_count: int, schema_backed_count: int, route_inventory_count: int) -> str:
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return "\n\n".join(
        [
            "Current MSA API inventory generated from repo-local docs and active runtime service route definitions.",
            f"Included active HTTP services: {service_count}",
            f"Included paths: {path_count}",
            f"Schema-backed services: {schema_backed_count}",
            f"Route-inventory fallback services: {route_inventory_count}",
            "Excluded by rule: front repos, empty shell repos, internal-only workers, and legacy monolith namespaces.",
            "Route and method inventory source: `docs/mappings/current-runtime-inventory.md`, `docs/mappings/repo-responsibility-matrix.md`, and local `development/service-*/**/urls.py` / `views.py`.",
            "Schema note: services without exported service-owned OpenAPI still fall back to route inventory only.",
            f"Generated at: {generated_at}",
        ]
    )


def default_response() -> dict[str, Any]:
    return {
        "default": {
            "description": "Current response payload depends on service implementation. Service-owned OpenAPI schema export is not attached yet."
        }
    }


def build_spec(services: list[ServiceMetadata]) -> dict[str, Any]:
    paths: dict[str, dict[str, Any]] = {}
    components: dict[str, dict[str, Any]] = {}
    tag_groups: dict[str, list[str]] = {group_name: [] for group_name in GROUP_ORDER}
    schema_backed_count = 0
    route_inventory_count = 0

    for service in services:
        tag_groups[tag_group_for_service(service.repo_name)].append(service.repo_name)
        schema_backed_artifact = load_schema_backed_paths(service)
        if schema_backed_artifact is not None:
            schema_backed_count += 1
            merge_components(components, schema_backed_artifact.components)
            for path, path_item in schema_backed_artifact.paths.items():
                paths[path] = path_item
            continue

        route_inventory_count += 1
        route_definitions = parse_leaf_routes(service)
        view_infos_by_file: dict[Path, dict[str, ViewClassInfo]] = {}

        for route in route_definitions:
            if route.views_path not in view_infos_by_file:
                view_infos_by_file[route.views_path] = parse_view_classes(route.views_path)
            view_info = view_infos_by_file[route.views_path][route.view_class_name]

            path_item = paths.setdefault(route.path, {})
            for method in route.methods:
                if method in path_item:
                    continue

                detail = bool(route.parameters)
                if route.urls_path.read_text(encoding="utf-8").find("include(router.urls)") != -1 and route.view_class_name.endswith("ViewSet"):
                    local_prefix = route.path.split(service.gateway_prefix.rstrip("/"))[-1].strip("/").split("/")[0]
                    summary = build_router_summary(local_prefix, method, detail=detail)
                else:
                    summary = build_path_summary(view_info, method)

                operation = {
                    "tags": [service.repo_name],
                    "summary": summary,
                    "description": route_description(route, view_info),
                    "operationId": f"{service.repo_name}.{route.view_class_name}.{method}",
                    "responses": default_response(),
                    "x-clever-owner-repo": service.repo_name,
                    "x-clever-compose-service": service.compose_service,
                    "x-clever-gateway-prefix": service.gateway_prefix,
                    "x-clever-source-of-truth-doc": "docs/mappings/current-runtime-inventory.md",
                    "x-clever-runtime-status": service.status,
                    "x-clever-schema-source": "route-inventory",
                }
                if route.parameters:
                    operation["parameters"] = route.parameters
                path_item[method] = operation

    ordered_paths = dict(sorted(paths.items(), key=lambda item: item[0]))
    ordered_tag_groups = [
        {"name": group_name, "tags": tags}
        for group_name, tags in tag_groups.items()
        if tags
    ]

    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "CLEVER Current MSA API",
            "version": dt.date.today().isoformat(),
            "description": info_description(len(services), len(ordered_paths), schema_backed_count, route_inventory_count),
        },
        "servers": [
            {
                "url": "http://localhost:8080",
                "description": "Local edge gateway",
            }
        ],
        "tags": [build_tag(service) for service in services],
        "x-tagGroups": ordered_tag_groups,
        "paths": ordered_paths,
    }
    if components:
        spec["components"] = components
    return spec


def build(output_path: Path) -> None:
    services = load_active_services()
    spec = build_spec(services)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(spec, file, allow_unicode=True, sort_keys=False, width=120)

    print(f"Built {output_path}")
    print(f"Services: {len(services)}")
    print(f"Paths: {len(spec['paths'])}")
    for service in services:
        schema_mode = "schema" if service_schema_path(service).exists() else "route"
        print(f"{service.repo_name}: {service.gateway_prefix} ({schema_mode})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the CLEVER current MSA unified OpenAPI artifact.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Path to write the generated OpenAPI YAML.")
    args = parser.parse_args()
    build(Path(args.output))


if __name__ == "__main__":
    main()
