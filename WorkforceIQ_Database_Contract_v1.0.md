# WorkforceIQ Database Contract v1.0 (Draft)

## Purpose

The purpose of `database.py` is to provide a single interface between WorkforceIQ modules and `workforce.db`.

### Rules

1. Modules never communicate directly with SQLite.
2. Modules never execute SQL.
3. Modules communicate with `database.py` using JSON requests.
4. `database.py` is responsible for CRUD operations.
5. Business logic remains in Service classes.
6. Validation remains in Service classes.
7. `database.py` only performs data storage and retrieval.

---

# Architecture

```text
app.py
    ↓
Routes
    ↓
Services
    ↓
Repositories
    ↓
database.py
    ↓
workforce.db
```

Example:

```text
EmployeeService
      ↓
EmployeeRepository
      ↓
database.py
      ↓
EMPLOYEES table
```

---

# Request Format

All requests sent to `database.py` follow the same structure.

```json
{
    "operation": "read",
    "table": "employees",
    "filters": {}
}
```

---

# Supported Operations

## Create

```json
{
    "operation": "create",
    "table": "employees",
    "data": {
        "first_name": "John",
        "last_name": "Smith",
        "role_id": 2,
        "hourly_rate": 18.50
    }
}
```

---

## Read

### Single Record

```json
{
    "operation": "read",
    "table": "employees",
    "filters": {
        "employee_id": 1
    }
}
```

### Filtered Query

```json
{
    "operation": "read",
    "table": "employees",
    "filters": {
        "active": true
    }
}
```

---

## Update

```json
{
    "operation": "update",
    "table": "employees",
    "filters": {
        "employee_id": 1
    },
    "data": {
        "hourly_rate": 20.00
    }
}
```

---

## Deactivate (Soft Delete)

```json
{
    "operation": "deactivate",
    "table": "employees",
    "filters": {
        "employee_id": 1
    }
}
```

Results in:

```sql
UPDATE employees
SET active = false
WHERE employee_id = 1;
```

---

# Success Response

### Create

```json
{
    "status": "success",
    "record_id": 17
}
```

### Read

```json
{
    "status": "success",
    "data": [
        {
            "employee_id": 1,
            "first_name": "John"
        }
    ]
}
```

### Update

```json
{
    "status": "success",
    "rows_affected": 1
}
```

---

# Error Response

```json
{
    "status": "error",
    "message": "Employee not found"
}
```

---

# Employee Management Examples

## Create Employee

```json
{
    "operation": "create",
    "table": "employees",
    "data": {
        "first_name": "Ana",
        "last_name": "Ruiz",
        "role_id": 2,
        "hourly_rate": 18.50,
        "max_hours_per_week": 40,
        "preferred_hours_per_week": 32,
        "active": true
    }
}
```

## Get Employee

```json
{
    "operation": "read",
    "table": "employees",
    "filters": {
        "employee_id": 7
    }
}
```

---

# Availability Management Examples

## Save Availability

```json
{
    "operation": "create",
    "table": "employee_availability",
    "data": {
        "employee_id": 7,
        "start_datetime": "2026-11-13T17:00:00",
        "end_datetime": "2026-11-13T23:00:00",
        "available": true
    }
}
```

## Get Availability

```json
{
    "operation": "read",
    "table": "employee_availability",
    "filters": {
        "employee_id": 7
    }
}
```

---

# Forecasting Examples

## Save Forecast

```json
{
    "operation": "create",
    "table": "forecasts",
    "data": {
        "forecast_date": "2026-11-09",
        "projected_sales": 4820.00,
        "projected_sales_low": 4210.00,
        "projected_sales_high": 5430.00,
        "required_labor_hours": 87.64,
        "labor_budget": 1349.60
    }
}
```

## Get Forecast

```json
{
    "operation": "read",
    "table": "forecasts",
    "filters": {
        "forecast_date": "2026-11-09"
    }
}
```

---

# Scheduling Examples

## Add Assignment

```json
{
    "operation": "create",
    "table": "shift_assignments",
    "data": {
        "schedule_id": 1,
        "employee_id": 7,
        "role_id": 2,
        "shift_id": 3,
        "hours": 8,
        "projected_cost": 148.00
    }
}
```

---

# Future Considerations

Potential operations:

```text
create
read
update
deactivate

bulk_create
bulk_update

begin_transaction
commit_transaction
rollback_transaction
```

---

# Team Guidance

Each module should focus on:

```text
Routes       → User requests
Services     → Business rules
Repositories → Build JSON request
Database     → Execute CRUD
SQLite       → Store data
```

Repositories should never generate SQL directly. Instead, repositories should construct request objects and pass them to `database.py`, making `database.py` the single source of truth for database access.

Benefits:

- Consistent database access
- Easier testing
- Lower module coupling
- Simpler future migration from SQLite to PostgreSQL
- Enables parallel development across modules