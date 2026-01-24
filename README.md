# School Agent Backend

Multi-tenant school management system built with FastAPI and PostgreSQL.

## Features

- **Multi-School Support**: Each school is a separate project (tenant)
- **Role-Based Access Control (RBAC)**: Granular permissions system
- **Attendance Management**: Track student attendance with Excel upload
- **Exam Management**: Record and analyze exam results with strict validation
- **Task Management**: Assign and track tasks to users or roles
- **Audit Logging**: Complete, append-only action history
- **In-App Notifications**: User notifications for important events

## Tech Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with SQLAlchemy async ORM
- **Authentication**: JWT (stateless)
- **File Handling**: Excel (XLSX only) via openpyxl
- **Package Manager**: UV

## Project Structure

```
backend/
├── alembic/                 # Database migrations
│   ├── versions/           # Migration files
│   └── env.py              # Alembic environment
├── app/
│   ├── api/                # API routers
│   │   └── v1/
│   │       ├── endpoints/  # Route handlers
│   │       └── router.py   # Main router
│   ├── core/               # Core utilities
│   │   ├── config.py       # Settings
│   │   ├── database.py     # DB connection
│   │   ├── dependencies.py # FastAPI dependencies
│   │   ├── exceptions.py   # Custom exceptions
│   │   └── security.py     # Auth utilities
│   ├── middleware/         # Custom middleware
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Business logic
│   └── main.py             # Application entry
├── alembic.ini             # Alembic config
├── pyproject.toml          # Project dependencies
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- UV package manager

### Installation

1. **Install UV** (if not already installed):
   ```powershell
   pip install uv
   ```

2. **Clone and navigate to the project**:
   ```powershell
   cd backend
   ```

3. **Create virtual environment and install dependencies**:
   ```powershell
   uv venv
   .\.venv\Scripts\activate
   uv sync
   ```

4. **Set up environment variables**:
   ```powershell
   Copy-Item .env.example .env
   # Edit .env with your database credentials and secret key
   ```

5. **Create the database**:
   ```powershell
   # Using psql or pgAdmin, create database:
   # CREATE DATABASE school_agent;
   ```

6. **Run database migrations**:
   ```powershell
   alembic upgrade head
   ```

7. **Start the development server**:
   ```powershell
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

8. **Access the API**:
   - API: http://localhost:8000
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Overview

All endpoints (except auth) require:
- `Authorization: Bearer <token>` header
- `X-Project-Id: <uuid>` header for project-scoped endpoints

### Modules

| Module | Prefix | Description |
|--------|--------|-------------|
| Auth | `/api/v1/auth` | Login, register, token refresh |
| Projects | `/api/v1/projects` | Project (school) management |
| Roles | `/api/v1/roles` | RBAC management |
| Tasks | `/api/v1/tasks` | Task management |
| Attendance | `/api/v1/attendance` | Attendance records |
| Exams | `/api/v1/exams` | Exam records |
| Uploads | `/api/v1/uploads` | Excel file uploads |
| Audit Logs | `/api/v1/audit-logs` | Action history |
| Notifications | `/api/v1/notifications` | In-app notifications |

## Upload Behavior

### Attendance Upload
- **Partial Success**: Invalid rows are skipped
- **Missing Student**: Allowed (new record created)
- **Upload metadata**: Always saved

### Exam Upload (STRICT)
- **Full Rollback**: Any invalid row triggers complete rollback
- **Validation**: `marks_obtained` must not exceed `max_marks`
- **Upload status**: Marked as failed on any error

## Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

### Error Codes

| Code | Description |
|------|-------------|
| `AUTH_FAILED` | Authentication failed |
| `PERMISSION_DENIED` | Insufficient permissions |
| `PROJECT_SUSPENDED` | Project is suspended |
| `VALIDATION_ERROR` | Request validation failed |
| `UPLOAD_FAILED` | File upload failed |
| `NOT_FOUND` | Resource not found |
| `INTERNAL_ERROR` | Internal server error |

## Development

### Creating a New Migration

```powershell
alembic revision --autogenerate -m "description of changes"
```

### Running Tests

```powershell
pytest
```

### Code Formatting

```powershell
ruff check --fix .
ruff format .
```

## Default Permissions

The system includes these permission keys:

- `attendance.*` - Attendance operations
- `exam.*` - Exam operations
- `task.*` - Task operations
- `role.*` - Role management
- `user.*` - User management
- `audit.view` - View audit logs
- `project.*` - Project settings

## License

Proprietary - All rights reserved
