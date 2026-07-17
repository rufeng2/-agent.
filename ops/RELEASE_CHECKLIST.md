# Production Release Checklist

## Before Maintenance

- Record the current image tag and Alembic revision.
- Verify production configuration with no repository default credentials.
- Run `python scripts/backup.py` and verify the backup manifest.
- Run backend tests, frontend build, Compose validation, dependency audit, and image scan.

## Migration And Deployment

1. Stop business traffic at Nginx.
2. For the first upgrade of an existing reviewed schema, run `alembic stamp 20260715_0001`.
3. Run `alembic upgrade head`.
4. Run `python scripts/bootstrap_admin.py` only when no administrator exists.
5. Start the versioned image using the production Compose overlay.
6. Require HTTP 200 from `/api/health/live` and `/api/health/ready`.
7. Run login, password rotation, dashboard, product list, conversation, approval, MCP status, and rollback smoke tests.
8. Restore Nginx traffic and watch error rate, P95 latency, MCP failures, approval conflicts, and rollback rate for 30 minutes.

## Rollback

- Stop the new image and start the recorded previous image.
- Do not run destructive Alembic downgrade commands.
- Restore the database only when the migration changed data incompatibly and the maintenance-window backup has been verified.
- Record request IDs, image versions, database revision, timestamps, and the rollback decision.
