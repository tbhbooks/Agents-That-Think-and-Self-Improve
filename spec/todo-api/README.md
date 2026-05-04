# todo-api

A small REST API for managing tasks. Used as the running example throughout the TBH book.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /tasks | List all tasks |
| POST | /tasks | Create a task |
| GET | /tasks/:id | Get a task by ID |
| PUT | /tasks/:id | Update a task |
| DELETE | /tasks/:id | Delete a task |
| POST | /auth/register | Register a user |
| POST | /auth/login | Log in, get a token |

## Running

```
# Install dependencies
# Copy env template: cp .env.example .env
# Start the server on port 3000
# Run tests
```

## Environment

Use a local `.env` file for runtime configuration. Do not hardcode secrets in source files.

Example:

```bash
cp .env.example .env
```

## Known Issues

This codebase intentionally contains bugs and gaps for the reader's agent to discover and fix.
