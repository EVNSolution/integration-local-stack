FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY development/service-account-access/requirements.txt /tmp/account-auth-requirements.txt
COPY development/service-driver-profile/requirements.txt /tmp/driver-profile-requirements.txt
COPY development/service-personnel-document-registry/requirements.txt /tmp/personnel-document-registry-requirements.txt
COPY development/service-organization-registry/requirements.txt /tmp/organization-master-requirements.txt
COPY development/service-delivery-record/requirements.txt /tmp/delivery-record-requirements.txt
COPY development/service-settlement-registry/requirements.txt /tmp/settlement-registry-requirements.txt
COPY development/service-settlement-payroll/requirements.txt /tmp/settlement-payroll-requirements.txt
COPY development/service-terminal-registry/requirements.txt /tmp/terminal-registry-requirements.txt
COPY development/service-telemetry-hub/requirements.txt /tmp/telemetry-hub-requirements.txt
COPY development/service-dispatch-registry/requirements.txt /tmp/dispatch-registry-requirements.txt
COPY development/service-region-registry/requirements.txt /tmp/region-registry-requirements.txt
COPY development/service-region-analytics/requirements.txt /tmp/region-analytics-requirements.txt
COPY development/service-announcement-registry/requirements.txt /tmp/announcement-registry-requirements.txt
COPY development/service-support-registry/requirements.txt /tmp/support-registry-requirements.txt
COPY development/service-notification-hub/requirements.txt /tmp/notification-hub-requirements.txt

RUN pip install --no-cache-dir \
    -r /tmp/account-auth-requirements.txt \
    -r /tmp/driver-profile-requirements.txt \
    -r /tmp/personnel-document-registry-requirements.txt \
    -r /tmp/organization-master-requirements.txt \
    -r /tmp/delivery-record-requirements.txt \
    -r /tmp/settlement-registry-requirements.txt \
    -r /tmp/settlement-payroll-requirements.txt \
    -r /tmp/dispatch-registry-requirements.txt \
    -r /tmp/region-registry-requirements.txt \
    -r /tmp/region-analytics-requirements.txt \
    -r /tmp/announcement-registry-requirements.txt \
    -r /tmp/support-registry-requirements.txt \
    -r /tmp/notification-hub-requirements.txt \
    -r /tmp/terminal-registry-requirements.txt \
    -r /tmp/telemetry-hub-requirements.txt

COPY development/service-account-access /workspace/services/account-auth
COPY development/service-driver-profile /workspace/services/driver-profile
COPY development/service-personnel-document-registry /workspace/services/personnel-document-registry
COPY development/service-organization-registry /workspace/services/organization-master
COPY development/service-delivery-record /workspace/services/delivery-record
COPY development/service-settlement-registry /workspace/services/settlement-registry
COPY development/service-vehicle-registry /workspace/services/vehicle-asset
COPY development/service-dispatch-registry /workspace/services/dispatch-registry
COPY development/service-region-registry /workspace/services/region-registry
COPY development/service-region-analytics /workspace/services/region-analytics
COPY development/service-announcement-registry /workspace/services/announcement-registry
COPY development/service-support-registry /workspace/services/support-registry
COPY development/service-notification-hub /workspace/services/notification-hub
COPY development/service-terminal-registry /workspace/services/terminal-registry
COPY development/service-telemetry-hub /workspace/services/telemetry-hub
COPY development/service-vehicle-assignment /workspace/services/driver-vehicle-assignment
COPY development/service-settlement-payroll /workspace/services/settlement-payroll
COPY development/integration-local-stack/infra/env /workspace/infra/env
COPY development/integration-local-stack/infra/docker/seed-runner/run-seed.sh /workspace/infra/docker/seed-runner/run-seed.sh

RUN chmod +x /workspace/infra/docker/seed-runner/run-seed.sh \
    && ln -s /workspace/infra/docker/seed-runner/run-seed.sh /usr/local/bin/run-seed.sh

ENTRYPOINT ["/usr/local/bin/run-seed.sh"]
