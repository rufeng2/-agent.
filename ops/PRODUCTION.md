# Minimal production baseline

## Optional services

Start security scanning, observability, or search only when needed:

    docker compose -f docker-compose.yml -f docker-compose.production.yml --profile security up -d
    docker compose -f docker-compose.yml -f docker-compose.production.yml --profile observability up -d
    docker compose -f docker-compose.yml -f docker-compose.production.yml --profile search up -d

Set CLAMAV_ENABLED=true after ClamAV is healthy. Prometheus is on port 9090 and
Grafana on port 3000. Run scripts/validate_opensearch.py after enabling search.

## Identity and authorization

Local login remains available. Configure OIDC_ISSUER, OIDC_CLIENT_ID,
OIDC_CLIENT_SECRET_FILE and OIDC_ENABLED=true for OIDC. Configure LDAP_SERVER,
LDAP_USER_DN_TEMPLATE and LDAP_ENABLED=true for LDAP. Roles are admin, editor,
viewer, and user. Mutating API requests are recorded in audit_logs.

## Secrets and privacy

Mount secret files read-only and set the matching NAME_FILE variables. Do not put
production values in .env. Personal export and erasure are available under
/api/operations/privacy. Conversation and audit retention are enforced daily.

## Backup, release, and rollback

Run python scripts/backup.py. Test restore quarterly in a separate environment
with python scripts/restore.py BACKUP --confirm RESTORE. Deploy with
scripts/deploy.ps1 -Version VERSION -Canary and rollback with scripts/rollback.ps1.
A canary here is a health-gated single-instance replacement; true traffic splitting
requires an ingress or service mesh.

## Verification gates

Required before release: pytest, frontend build, Compose config validation,
integration smoke test, ecommerce Agent evaluation baseline comparison, and Locust load profile.
The project supplies the mechanisms; organization-specific SLOs, IdP credentials,
alert receivers, legal retention periods, and disaster-recovery drills still need
to be configured by the operator.
