# WorkforceIQ Development Quick Reference (Draft v1)

## Purpose
Provide a consistent workflow, module structure, and GitHub process so everyone knows:

- Where code belongs
- How work is tracked
- How code moves into `main`
- How WorkforceIQ aligns with the SDS
- How modules can be developed in parallel without creating dependencies

---

# SDS Design Principle

## Modules Communicate Through Services, Not Tables

Modules do **not** directly access another module's database tables.

Instead:

```text
Module A
   ↓
ModuleAService
   ↓ JSON
ModuleBService
   ↓
Module B
```

Example:

```python
employees = EmployeeService.get_employees()
```

Returns:

```json
[
  {
    "employee_id": 1,
    "first_name": "John",
    "role_id": 2
  }
]
```

Scheduling consumes Employee data through EmployeeService.

Scheduling does **not** query Employee tables directly.

### Benefits

✅ Reduced coupling

✅ Clear module boundaries

✅ Easier testing

✅ Easier maintenance

✅ Parallel development

✅ Future API readiness

✅ Less merge conflict risk

This means:

- Stephen can build Employee Management.
- Leia can build Availability.
- Merrill can build Scheduling.

As long as the JSON contracts are agreed upon, all three modules can be developed independently.

---

# 1. Start with a GitHub Issue

Every task begins with an Issue.

Examples:

```text
US-3 Employee Profiles
US-4 Employee Availability
US-7 Two-Week Staffing Forecast
```

---

# 2. Sync Your Repository

```bash
git checkout main
git pull origin main
```

---

# 3. Create a Branch

## Branch Naming Convention

Use the User Story, not developer names.

Examples:

```text
US-3-employee-profiles
US-4-employee-availability
US-7-staffing-forecast
US-10-ai-assistant
```

Create the branch:

```bash
git checkout -b US-4-employee-availability
```

Verify current branch:

```bash
git branch
```

---

# 4. Standard Module Structure

Every module follows the same layout:

```text
<module>/

├── <Module>Routes.py
├── <Module>Service.py
├── <Module>Repository.py
├── <Module>Tests.py
└── templates/
```

Example:

```text
authentication/

├── AuthenticationRoutes.py
├── AuthenticationService.py
├── AuthenticationRepository.py
├── AuthenticationTests.py
└── templates/
```

---

# 5. File Responsibilities

| File | Purpose |
|--------|--------|
| Routes | Flask routes, requests, responses |
| Service | Business rules, validation, workflow, JSON contracts |
| Repository | Database access (SQL only) |
| Templates | Module UI |
| Tests | Module verification |
| app.py | Startup and module registration |
| database/init_db.py | Database creation |
| database/connection.py | Shared DB access |

---

# 6. Development Workflow

## Build Order

1. Repository
2. Service
3. Routes
4. Templates
5. Tests

### Routes

Responsible for:

- Requests
- Responses
- Redirects
- Templates
- JSON responses

**No SQL**

### Services

Responsible for:

- Validation
- Business Rules
- Calculations
- Workflow Logic
- Module-to-Module JSON Contracts

**No SQL**

### Repositories

Responsible for:

- SELECT
- INSERT
- UPDATE
- DELETE

**No Business Logic**

---

# 7. Commit & Push

Stage changes:

```bash
git add .
```

Commit changes:

```bash
git commit -m "US-4 Add AvailabilityService"
```

Push branch:

```bash
git push -u origin US-4-employee-availability
```

Commit often and keep commits focused.

---

# 8. Create a Pull Request

## Option A: GitHub Website

1. Open the WorkforceIQ repository.
2. Select **Pull Requests**.
3. Click **New Pull Request**.
4. Set:

```text
Base Branch: main
Compare Branch: US-4-employee-availability
```

5. Click **Create Pull Request**

### PR Title

```text
US-4 Employee Availability MVP
```

### PR Description

```text
Summary
-------
Implemented Availability MVP.

Changes
-------
- Added AvailabilityRepository
- Added AvailabilityService
- Added AvailabilityRoutes
- Added AvailabilityTests

Testing
-------
- Manual testing completed
- Tests passing

SDS Alignment
-------------
Follows Routes → Service → Repository pattern.
```

---

## Option B: GitHub CLI

### One-Time Setup

```bash
gh --version
gh auth login
```

### Create Pull Request

```bash
gh pr create
```

Or:

```bash
gh pr create \
  --base main \
  --title "US-4 Employee Availability MVP" \
  --body "Added AvailabilityRepository, AvailabilityService, AvailabilityRoutes, and AvailabilityTests."
```

### View Pull Requests

```bash
gh pr list
```

```bash
gh pr view
```

### Review Another Developer's PR

```bash
gh pr checkout <PR_NUMBER>
```

Example:

```bash
gh pr checkout 12
```

---

# 9. Review & Merge

## Review Checklist

- [ ] SDS aligned
- [ ] Correct module used
- [ ] Routes / Service / Repository separation maintained
- [ ] JSON contract defined (where applicable)
- [ ] Tests included
- [ ] Existing functionality still works
- [ ] Peer review completed

### Merge in GitHub

1. Open Pull Request
2. Click **Merge Pull Request**
3. Click **Confirm Merge**
4. Close associated Issue

### Merge with GitHub CLI

```bash
gh pr merge <PR_NUMBER> --merge
```

Example:

```bash
gh pr merge 12 --merge
```

Alternative merge options:

```bash
gh pr merge 12 --squash
```

```bash
gh pr merge 12 --rebase
```

---

# 10. Close Issue

GitHub UI:

```text
Close Issue after merge
```

GitHub CLI:

```bash
gh issue close <ISSUE_NUMBER>
```

Example:

```bash
gh issue close 5 --comment "Completed in PR #12"
```

---

# 11. Local Cleanup

After merge:

```bash
git checkout main
git pull origin main
git branch -d US-4-employee-availability
```

Delete remote branch in GitHub if not automatically removed.

---

# 12. Proposed Repository Structure

```text
app.py

authentication/
user_management/
employee_management/
availability/
forecasting/
scheduling/
ai_assistant/

database/
├── connection.py
├── init_db.py
└── workforce.db

static/
docs/
diagrams/
```

---

# 13. Alpha MVP Goal

| Module | MVP Goal |
|----------|----------|
| Authentication | Login / Registration |
| User Management | User ↔ Employee Link |
| Employee Management | Employee CRUD |
| Availability | Availability Tracking |
| Forecasting | Basic Forecast |
| Scheduling | Draft Schedule |
| AI Assistant | Shift Coverage Query |

---

# Quick Workflow Summary

```text
Issue
  ↓
Checkout Main
  ↓
Pull Latest Changes
  ↓
Create Branch
  ↓
Build Repository
  ↓
Build Service
  ↓
Build Routes
  ↓
Build Templates
  ↓
Write Tests
  ↓
Commit
  ↓
Push
  ↓
Create Pull Request
  ↓
Review
  ↓
Merge
  ↓
Close Issue
  ↓
Delete Branch
```

---

# Guiding Principle

**We are not replacing existing work. We are creating a stronger, SDS-aligned foundation so future development is easier, dependencies are clearer, modules can be developed concurrently, and WorkforceIQ can continue to grow without creating unnecessary technical debt.**