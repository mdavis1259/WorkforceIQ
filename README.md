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
- AI-assisted workforce questions
- Automated testing
- GitHub Actions CI/CD integration

---

# Requirements

## Python

Python 3.11 or later.

## Ollama

The AI Assistant requires Ollama and the Llama 3.2 model.

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

The AI Assistant can answer workforce-related questions using application data.

Example questions:

- How many employees are there?
- List all employees.
- What is each employee's hourly rate?
- What is the average employee wage?
- Which employee has the highest wage?

The AI Assistant uses Ollama and Llama 3.2 running locally.

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

- Workforce-related questions
- Local LLM integration
- Workforce data context

---

# Known Limitations

This Alpha Release is intended for demonstration and evaluation purposes.

Current limitations include:

- SQLite development database
- Basic forecasting model
- Limited reporting functionality
- Limited schedule optimization rules
- Ongoing SDS feature implementation

---

# Project Status

WorkforceIQ is currently in the Alpha Release phase.

Current focus areas include:

- Forecast refinement
- Schedule optimization
- Reporting features
- Administrative workflows
- Expanded AI capabilities
- SDS compliance enhancements

---

# Educational Use Notice

WorkforceIQ is an educational software project developed for the CMSC 495 Computer Science Capstone course.

The application is intended for academic and demonstration purposes and is not currently intended for production workforce management operations.
