# WorkforceIQ

WorkforceIQ is an AI-assisted workforce planning and scheduling platform being developed as part of the CMSC 495 Computer Science Capstone course.

## Team

- Merrill Davis
- Stephen Douba
- Leia Gabriele

## Current Repository

This repository currently contains a proof of concept demonstrating:

- Flask web application
- Employee management prototype
- Demand forecasting prototype
- AI assistant integration using Ollama and Llama 3.2
- SQLite database

## Requirements

### Python

Python 3.11+

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

## Running the Application

Install dependencies:

```bash
pip install -r requirements.txt
```

Initialize the database:

```bash
python init_db.py
```

Run the application:

```bash
python app.py
```

Then open:

```text
http://localhost:5000
```

## EMPLOYEE MODULE
The Employee Module currently will route to a table of current employees with a feature to add employees.  In the full version there will be a full CRUD implementation to allow for updating and removing employees.

## FORECASTING MODULE
The Forecasting Module currently will route to a summary of the scikit-learn output from a sample dataset included in app.py.

## REPORTS MODULE
Under construction.

## AI ASSISTANT MODULE
The AI Assistant Module currently will route to a prompt where you can ask the llama3.2 model through Ollama questions about the Employees table, such as:
  * How many employees are there?
  * What is each employee's wages?
  * List all employee data.
  * What is the average wage for all employees?
The model should respond in less than 10 seconds.

## Notes

This repository currently contains a proof of concept used to demonstrate WorkforceIQ's core concepts. The architecture, database schema, and project organization will be refined as the team progresses through the capstone project.

Feel free to explore the code, try the current features, and share feedback and ideas for future development.