# WorkforceIQ

WorkforceIQ is an AI-assisted workforce planning and scheduling platform developed as part of the CMSC 495 Computer Science Capstone course.

The WorkforceIQ Alpha Release demonstrates integrated workforce forecasting, scheduling, employee management, user administration, and AI-assisted workforce analysis through a unified web application.

---

# Team

- Merrill Davis
- Stephen Douba
- Leia Gabriele

---

# Repository Workflow

The WorkforceIQ team uses a collaborative Git workflow designed to maintain code quality and project stability.

## Development Process

- Create feature branches for all development work.
- Submit completed work through Pull Requests (PRs).
- Review code prior to merging whenever possible.
- Avoid direct development on the `main` branch.
- Avoid force pushes to shared branches.

Example workflow:

```bash
git checkout -b feature-branch
git add .
git commit -m "Implement feature"
git push -u origin feature-branch
```

---

# Alpha Release Overview

The Alpha Release demonstrates:

- Authentication and user login
- Employee management
- User management
- Employee availability management
- Demand forecasting
- Labor budget forecasting
- Staffing requirements management
- Automated schedule generation
- Labor cost analysis
- AI Assistant for shift availability and qualification questions
- Automated testing
- GitHub Actions CI/CD integration

---

# Time-off requests

On the availability calendar, select **New Time-Off Request** and choose an
inclusive start and end date. Saving creates a pending request and displays it
as a yellow background on the calendar. Managers and administrators create
requests from their own availability view; the button is hidden when viewing
another employee's availability. Dates cannot be before today; the server
validates today using its local time zone. Requests cannot overlap any existing
non-cancelled request for the same employee.
Managers and administrators can review pending requests on another employee's
availability calendar.

---

# Requirements

## Python

Python 3.11 or later.

## Ollama

The AI Assistant requires Ollama and the Llama 3.2 model.
If Ollama is not running, the assistant falls back to a simpler keyword parser and still answers supported questions.

Install Ollama:

<https://ollama.com>

Pull the model:

```bash
ollama pull llama3.2
```

Verify installation:

```bash
ollama list
```

Expected output:

```text
llama3.2
```

---

# Installation

Clone the repository:

```bash
git clone <repository-url>
cd workforceiq
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Initialize the database:

```bash
python database/init_db.py
```

Start the application:

```bash
python app.py
```

Open:

```text
http://localhost:5000
```

---

# Running Tests

Run the full test suite:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Run Forecasting tests:

```bash
python -m unittest forecasting.ForecastTests -v
```

Run Scheduling tests:

```bash
python -m unittest scheduling.SchedulingTests -v
```

Run User Management tests:

```bash
python -m unittest user_management.UserTests -v
```

---

# Continuous Integration

WorkforceIQ uses GitHub Actions for Continuous Integration.

The CI/CD pipeline automatically:

- Installs project dependencies
- Initializes the application database
- Executes automated tests
- Validates pull requests prior to merge

All code intended for release should successfully pass the CI/CD pipeline.

---

# Application Workflow
> **Important:** WorkforceIQ follows a forecast-driven scheduling process.
> Staffing Requirements should be configured first, followed by Forecast generation and Forecast approval.
> Schedules should only be generated after a forecast has been reviewed and approved by a Manager.


The WorkforceIQ Alpha Release is intended to be used in the following order.

## 1. Login

Log in using a Manager or Administrator account.

---

## 2. Configure Staffing Requirements

Define staffing requirements based on:

- Workday
- Shift
- Role
- Required staffing levels

These requirements serve as the basis for schedule generation.

---

## 3. Generate Forecasts

Navigate to the Forecasting module and generate a draft forecast.

Forecasts provide:

- Projected sales
- Forecast high and low ranges
- Labor budget estimates

---

## 4. Review and Approve Forecasts

**Forecast approval is a required step before schedule generation.**

After generating a forecast, managers should review:

- Projected sales
- Forecast ranges
- Labor budget estimates

If necessary, forecast values may be adjusted prior to approval.

Only approved forecasts should be used for schedule generation. The Scheduling module relies on approved forecast data when evaluating labor budgets and labor variance reporting.

**WorkforceIQ operational workflow:**

1. Configure Staffing Requirements
2. Generate Draft Forecast
3. Review Forecast
4. Approve Forecast
5. Generate Schedule
6. Review Labor Analysis


---

## 5. Generate Weekly Schedules

After forecasts are approved, generate a weekly schedule.

The scheduling engine evaluates:

- Staffing requirements
- Employee qualifications
- Employee availability
- Weekly hour limits
- Shift conflicts

---

## 6. Review Labor Analysis

After schedule generation, managers can review:

- Scheduled labor cost
- Forecasted labor budget
- Labor variance analysis

This helps evaluate whether generated schedules align with planned labor spending.

---

## 7. Use the AI Assistant

Open **AI Assistant** in the navigation bar. It is available to Managers and Administrators and is read-only: it never changes data.

### Questions the assistant can answer in this Alpha

| Question type | Example | What you get |
|---|---|---|
| Who is available for a shift | "Who is available to cover the Friday evening shift?" | Employees marked available for that shift, with their role |
| Who is qualified | "Who is qualified as an associate?" or "Who is qualified for the evening shift on Friday?" | Employees with that role or qualification (and available, if a shift is named) |

Tips for good questions:

- Name the day: a weekday (Friday), `today`, `tomorrow`, or a date like `2026-11-20`.
- Name the shift: the morning, afternoon, or evening shift.
- Optionally name a role or qualification, such as Associate or First Aid / CPR.
- Questions must be 3 to 500 characters.

If the question is missing a detail, the assistant asks for it (for example, "Which day do you mean?"). If it is not one of the supported types, it lists the supported types.

### Not available in this Alpha

- **Budget questions** (for example, "Is next week within budget?"). The assistant replies that the budget check is not available yet. Connecting it to the Scheduling and labor cost data is planned after the Alpha.
- Questions about wages or hourly rates. Wages are never sent to the AI model or shown in its answers.
- Changing schedules or employee records.

### How it works

Llama 3.2 (through Ollama) only works out what the manager is asking. The answer itself always comes from the database and is re-checked against availability and qualification rules. If Ollama is not running or returns unusable output, a keyword parser answers the question and the page shows a notice that the AI model was not available.

---

# Current Modules

## Authentication

- Login
- Session management
- Role-based access

## Employee Management

- Employee profiles
- Employee management
- Employee search

## User Management

- User account management
- Role assignment
- Password reset workflow
- Account activation and deactivation

## Availability Management

- Employee availability tracking
- Scheduling support

## Forecasting

- Historical demand analysis
- 14-day forecasting
- Labor budget forecasting
- Draft and Approved forecast workflow

## Scheduling

- Staffing requirements management
- Schedule generation
- Assignment management
- Labor cost analysis

## AI Assistant

- Answers availability and qualification questions for a shift
- Pipeline: intent parsing, query planning, rule validation, response building
- Local Llama 3.2 through Ollama, with a keyword-parser fallback
- Read-only and manager-only; no employee records or wages are sent to the model
- Budget questions are not connected yet (see Known Limitations)
- Endpoints: `POST /api/assistant/query` and `GET /api/assistant/health`

---

# Known Limitations

This Alpha Release is intended for demonstration and evaluation purposes.

Current limitations include:

- SQLite development database
- Basic forecasting model
- Limited reporting functionality
- Limited schedule optimization rules
- Ongoing SDS feature implementation
- AI Assistant budget questions are not connected to scheduling data yet
- AI Assistant availability matches the weekly shift pattern, not individual dates

---

# Project Status

WorkforceIQ is currently in the Alpha Release phase.

Current focus areas include:

- Forecast refinement
- Schedule optimization
- Reporting features
- Administrative workflows
- Expanded AI capabilities, starting with budget questions
- SDS compliance enhancements

---

# Educational Use Notice

WorkforceIQ is an educational software project developed for the CMSC 495 Computer Science Capstone course.

The application is intended for academic and demonstration purposes and is not currently intended for production workforce management operations.
