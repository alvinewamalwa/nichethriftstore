
# Niche Thrift Store

A small online thrift store being developed with Flask, Python, SQLite, HTML, and CSS.

## Project status

The project is under active development. The initial milestone covers the application structure, database schema, homepage, and health endpoint.

The catalogue, shopping cart, order requests, and owner administration will be added in later milestones.

## Technology stack

- Python
- Flask
- SQLite
- HTML and CSS
- pytest

## Local setup

### 1. Create and activate the virtual environment

On Linux or WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install -r requirements-dev.txt
```

### 3. Initialise the database

```bash
flask --app app init-db
```

### 4. Run the application

```bash
flask --app app run --debug
```

Open http://127.0.0.1:5000 in your browser.

### 5. Run the tests

In a second terminal, activate the virtual environment and run:

```bash
python -m pytest -v
```

## Health check

Visit http://127.0.0.1:5000/healthz.

A healthy application should return HTTP 200 and:

```json
{"status": "ok"}
```

The health endpoint checks that the database and expected schema are available.

## Database

The local SQLite database is stored under the `instance/` directory. Database files are excluded from Git.

For development, back up any data you need before resetting or deleting the database. Schema changes may require a database migration or a fresh development database.

## Development principles

- Keep the project free of unapproved paid services.
- Do not commit passwords, secret keys, environment files, or private customer information.
- Verify changes with tests before committing them.
- Online payments are not part of the initial MVP.
