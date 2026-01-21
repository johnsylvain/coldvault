# Product Spec: ColdVault
**Self-Hosted Scheduled Backups to AWS Cold Storage (Docker, Dashboard, Set-and-Forget)**

---

## 1. Overview

ColdVault is a self-hosted Docker application that provides **automated, encrypted, scheduled backups** from a single host (e.g. a Lenovo ThinkCentre running OMV + Docker) to **AWS cold storage** (S3 Glacier classes).

It supports **multiple datasets with independent schedules**, **manual backup triggers**, **host-level backups (via restic)**, and a **dashboard** for monitoring backup health, storage usage, and estimated costs.

ColdVault is designed to be:
- Easy to install via Docker
- Safe by default
- Low maintenance (“set it and forget it”)
- Suitable for homelabs with media servers (Plex, Immich, etc.)

---

## 2. Goals

- Back up **multiple data categories** with **different backup intervals**
- Support both:
  - Dataset-level backups (media, Immich, app data)
  - Full host/system backups (ThinkCentre)
- Provide a **single dashboard** for visibility and control
- Target **AWS cold storage** to minimize long-term costs
- Enable **manual backups on demand**
- Favor **reliability and recoverability** over raw speed

---

## 3. Non-Goals (Initial Scope)

- Replacing NAS or file sharing
- Real-time replication
- Multi-node clustering
- Non-AWS storage targets (future scope)
- Continuous versioning of frequently changing files

---

## 4. Primary Use Cases

### UC1 — Media Backup (Plex)
- Music, TV, movies
- Mostly static data
- Backed up weekly or monthly
- Stored in Glacier Deep Archive
- Restore is rare but acceptable to take time

### UC2 — Immich Backup
- Photos, videos, metadata, database dumps
- Moderately changing data
- Backed up daily
- Stored in Glacier Flexible or Instant Retrieval
- Higher restore priority

### UC3 — ThinkCentre Host Backup
- OS-level data (configs, `/etc`, `/home`, Docker volumes)
- Uses **restic**
- Snapshot-based
- Backed up nightly or weekly
- Stored in cold storage for disaster recovery

### UC4 — Manual Backup
- User clicks “Run now” in dashboard
- Immediate execution with live logs
- Useful before system changes or upgrades

---

## 5. Functional Requirements

### FR1 — Backup Jobs

Each backup job must support:
- One or more source paths
- Independent schedules
- Manual execution
- Incremental snapshots
- Include/exclude rules
- Bandwidth limiting
- CPU/IO priority control

Job types:
- `dataset` (e.g. media, Immich)
- `host` (ThinkCentre system backup)

---

### FR2 — Scheduling

- Cron-like scheduling per job
- Presets:
  - Hourly
  - Daily
  - Weekly
  - Monthly
- Manual trigger from dashboard
- Protection against overlapping runs

---

### FR3 — Storage Targets

- AWS S3 bucket with selectable storage class:
  - Glacier Instant Retrieval
  - Glacier Flexible Retrieval
  - Glacier Deep Archive
- Optional lifecycle strategy:
  - Upload to S3 Standard
  - Auto-transition to Glacier after N days
- Bucket prefix isolation per job

---

### FR4 — Retention Policies

Per-job retention configuration:
- Keep last N snapshots
- GFS-lite presets:
  - Daily / Weekly / Monthly
- Dry-run preview before retention changes
- Optional immutable retention (Object Lock)

---

### FR5 — Encryption & Security

- Client-side encryption enabled by default
- Encryption key stored via:
  - Docker secrets (preferred)
  - Environment variables (warned)
- Optional AWS KMS integration (future)
- Least-privilege IAM policy guidance

---

### FR6 — Restic Integration (Host Backups)

- Native support for restic-based jobs
- Restic repository stored in S3
- Supports:
  - System directories
  - Docker volumes
  - Application configs
- Excludes ephemeral paths by default:
  - `/proc`, `/sys`, `/dev`, caches
- Periodic `restic check` verification jobs

---

### FR7 — Restore

Restore capabilities:
- Browse snapshots per job
- Restore:
  - Single file/folder
  - Entire snapshot
- Restore to alternate path
- Glacier-aware workflow:
  - Retrieval required notice
  - Estimated wait time
  - Cost warning
- Export restore instructions for disaster recovery

---

### FR8 — Dashboard

#### Overview
- Job list with:
  - Last run status
  - Last successful backup
  - Next scheduled run
- Health indicators (green/yellow/red)

#### Per Job View
- Run history
- Snapshot list
- Size and duration
- Logs (view + download)
- Retention state

#### Storage & Cost
- Stored bytes per job
- Storage class breakdown
- Estimated monthly cost
- Estimated retrieval costs
- Optional real AWS spend via Cost Explorer

---

### FR9 — Notifications

Alert conditions:
- Backup failure
- Missed schedule
- Verification failure
- Cost threshold exceeded

Delivery channels:
- Email (SMTP)
- Webhooks (Discord, Slack, generic)

---

## 6. Architecture

### Components

- **Web UI + API**
- **Scheduler**
- **Worker / Executor**
- **Metadata Store**
  - SQLite (MVP)
  - Postgres (recommended for growth)
- **Backup Engines**
  - Incremental snapshot engine (dataset jobs)
  - Restic engine (host jobs)

---

### Data Flow

Source Paths
↓
Snapshot / Restic
↓
Client-side Encryption
↓
S3 Upload (optional staging class)
↓
Lifecycle → Glacier
↓
Metadata Update
↓
Notification


---

## 7. AWS Integration

### Required AWS Services
- S3
- (Optional) Cost Explorer
- (Optional) KMS

### IAM Principles
- Bucket- and prefix-scoped permissions
- No wildcard account access
- Optional separate role per job

---

## 8. Reliability & Safety

- No destructive operations without confirmation
- Retention applied only after successful backup
- Locking to prevent concurrent runs
- Automatic retries with backoff
- Verification jobs:
  - Repository integrity checks
  - Optional sample restore validation

---

## 9. Deployment

### Installation
- Docker Compose
- Single container (MVP)
- Persistent volumes:
  - `/config`
  - `/cache`
- Read-only mounts for source data when possible

### Example Compose
```yaml
services:
  coldvault:
    image: coldvault/coldvault:1.0.0
    ports:
      - "8088:8088"
    volumes:
      - ./config:/config
      - ./cache:/cache
      - /mnt:/mnt:ro
    environment:
      - TZ=America/Chicago
    restart: unless-stopped

10. MVP Scope

Must-have:

Multiple jobs with independent schedules

Manual run from dashboard

Incremental dataset backups

Restic host backups

AWS Glacier support

Dashboard with health + cost estimates

Restore workflow

Email + webhook alerts

Post-MVP:

Object Lock

Prometheus metrics

Multiple backup targets

Multi-user/RBAC

Remote agents

11. Acceptance Criteria

User can deploy via Docker in <15 minutes

Media, Immich, and host backups can run on different schedules

Manual backups are triggered from the UI

Restore is possible without SSH access

Cost estimates reflect storage growth

Alerts fire reliably on failure

12. Open Questions (Optional)

Preferred Glacier class per dataset?

Desired restore SLA for Immich vs media?

Want optional second target (USB/offsite)?
