# WorkforceIQ Data Contract Architecture v1.0 (Draft)

## Purpose

The purpose of the WorkforceIQ Data Layer is to isolate database storage details from the rest of the application while allowing modules to exchange data through well-defined contracts.

Per the SDS:

```text
Routes
    ↓
Services
    ↓
Repositories
    ↓
SQLite
```

Repository classes form the Data Layer and are responsible for all SQL operations.

Services consume contract/domain objects and never access database tables directly.

---

# Architecture

```text
Browser
    ↓
Routes
    ↓
Services
    ↓
Repositories
    ↓
SQLite
```

Module communication:

```text
SchedulingService
        ↓
EmployeeService
        ↓
EmployeeRepository
        ↓
SQLite
```

Modules communicate through Services.

Repositories communicate with SQLite.

Modules never access another module's tables directly.

---

# Layer Responsibilities

## Routes

Responsible for:

```text
HTTP requests
HTTP responses
Templates
JSON API responses
Redirects
```

Must not contain:

```text
SQL
Business rules
```

---

## Services

Responsible for:

```text
Business rules
Validation
Calculations
Workflow logic
Module-to-module communication
```

Examples:

```text
Authentication
Scheduling rules
Availability validation
Forecast calculations
```

Must not contain:

```text
SQL
Database schema knowledge
```

---

## Repositories

Responsible for:

```text
SELECT
INSERT
UPDATE
DELETE
Transactions
```

Repositories own all SQL operations.

Must not contain:

```text
Business rules
Workflow logic
Authorization decisions
```

---

## SQLite

Responsible for:

```text
Data persistence
Indexes
Constraints
Relationships
Storage
```

SQLite knows nothing about WorkforceIQ business rules.

---

# Data Contracts

Per SDS Section 8.7:

```text
Data passes between modules as simple read-only objects
instead of raw database rows.
```

Repositories should translate database rows into WorkforceIQ contract objects.

---

# Repository Pattern

## Current State

```text
SQLite Row
      ↓
UserRepository
      ↓
sqlite3.Row
      ↓
UserService
```

## SDS-Aligned State

```text
SQLite Row
      ↓
UserRepository
      ↓
User Object
      ↓
UserService
```

The Service Layer should never need to know how SQLite stores the data.

---

# User Contract Example

```python
User(
    userid=1,
    username="mdavis",
    system_role_id=2,
    employee_id=12
)
```

Services consume:

```python
user.username
user.system_role_id
```

rather than:

```python
row["username"]
row["system_role_id"]
```

---

# Repository Example

```python
def get_user_by_id(self, user_id):

    cursor.execute(...)

    row = cursor.fetchone()

    if row is None:
        return None

    return User(
        userid=row["userid"],
        username=row["username"],
        system_role_id=row["system_role_id"],
        employee_id=row["employee_id"]
    )
```

---

# WorkforceIQ Contract Objects

The SDS currently defines the following contract types:

```text
User
Employee
AvailabilityEntry
Forecast
Assignment
RuleViolation
AssistantResponse
```

These objects should be exchanged between Services rather than passing raw database rows between modules.

---

# Connection Management

`connection.py` remains responsible only for:

```python
get_db_connection()
```

Responsibilities:

```text
Open SQLite connection
Configure connection settings
Close connection
```

`connection.py` is infrastructure, not a separate architecture layer.

---

# Team Guidance

Each module should focus on:

```text
Routes       → User requests and responses
Services     → Business rules and workflow logic
Repositories → SQL and object mapping
SQLite       → Data persistence
```

Repositories should:

```text
Convert SQLite rows to contract objects
Convert contract objects to SQLite records
```

Services should:

```text
Consume contract objects
Not consume sqlite3.Row objects directly
```

Modules should communicate through Services and contract objects rather than database tables.

---

# Future Considerations

Potential contract objects:

```text
User
Employee
AvailabilityEntry
Forecast
Assignment
RuleViolation
AssistantResponse
```

Potential future improvements:

```text
Immutable contract objects
Dataclasses
Type hints
Repository unit tests
SQLite/PostgreSQL portability
```

---

# Guiding Principle

```text
Routes handle requests.

Services enforce business rules.

Repositories own SQL and data translation.

SQLite stores data.

Modules exchange contract objects,
not database rows.
```
