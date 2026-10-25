# WorkforceIQ

WorkforceIQ is an AI-assisted workforce planning and scheduling platform being developed as part of the CMSC 495 Computer Science Capstone course.

## Team

- Merrill Davis
- Stephen Douba
- Leia Gabriele

---

## Current Repository

This repository currently contains a proof of concept demonstrating:

- Flask web application
- Employee management prototype
- Demand forecasting prototype
- AI assistant integration using Ollama and Llama 3.2
- SQLite database

---

## Requirements

### Python

Python 3.11 or later

### Ollama

Install Ollama:

https://ollama.com

Pull the model:

```bash
ollama pull llama3.2
```

Verify installation:

```bash
ollama list
```

You should see:

```text
llama3.2
```

---

## Quick Start

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

Run the application:

```bash
python app.py
```

Open your browser and navigate to:

```text
http://localhost:5000
```

---

## Current Modules

### Authentication

The application currently supports user login using credentials stored in a local SQLite database.

Future enhancements may include:

- User registration
- Password hashing
- Role-based permissions
- Session management

---

### Employee Module

The Employee Module currently displays a list of employees and provides functionality to add employees.

Planned enhancements include:

- Full CRUD operations
- Employee qualifications
- Employee availability
- Time-off requests
- Employee search and filtering

---

### Forecasting Module

The Forecasting Module currently demonstrates a simple scikit-learn forecasting model using sample data included in `app.py`.

The proof of concept forecasts:

- Projected demand
- Recommended staffing levels

Future enhancements may include:

- Historical sales imports
- Labor percentage goals
- Labor cost forecasting
- Multi-week forecasting

---

### Reports Module

Placeholder for future reporting functionality.

Potential reports include:

- Labor cost analysis
- Staffing utilization
- Forecast accuracy
- Schedule compliance

---

### AI Assistant Module

The AI Assistant currently integrates with the local Ollama-hosted Llama 3.2 model.

The assistant uses data from the Employees table as context when generating responses.

Example questions:

- How many employees are there?
- List all employees.
- What is each employee's wage?
- What is the average employee wage?
- Which employee has the highest wage?

The purpose of this feature is to demonstrate how WorkforceIQ may use AI to answer workforce-related questions using application data.

---

## Project Status

This repository contains a working proof of concept intended to demonstrate the core ideas behind WorkforceIQ.

Current focus areas include:

- Authentication
- Employee management
- AI-assisted workforce questions
- Forecasting concepts
- Application usability

The architecture, database schema, and repository organization will evolve as the team progresses through the capstone project.

---

## Notes

This project is an educational prototype and does not currently use real employee data, payroll systems, or production forecasting models.

Team members are encouraged to:

- Explore the code
- Test existing features
- Suggest improvements
- Discuss architecture and implementation ideas

As development progresses, the repository will evolve from a proof of concept into the full WorkforceIQ application.
