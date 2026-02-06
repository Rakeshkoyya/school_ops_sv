# School Ops Backend

FastAPI backend for the School Operations management system.

> 📖 **For complete setup instructions, see the main [README.md](../README.md) in the project root.**

## Quick Reference

### Development Commands

```powershell
# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start PostgreSQL (Docker)
docker-compose up -d
```

### Project Structure

```
backend/
├── alembic/                 # Database migrations
│   └── versions/           # Migration files
├── app/
│   ├── api/v1/             # API routers & endpoints
│   ├── core/               # Config, DB, security
│   ├── middleware/         # Custom middleware
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Business logic
│   └── main.py             # Application entry
├── .env.example            # Environment template
├── alembic.ini             # Alembic config
├── docker-compose.yml      # PostgreSQL container
└── pyproject.toml          # Dependencies
```

### API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Useful Commands

```powershell
# Create new migration
uv run alembic revision --autogenerate -m "description"

# Downgrade migration
uv run alembic downgrade -1

# Check migration status
uv run alembic current

# Run linting
uv run ruff check .

# Run type checking
uv run mypy app
```

### Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET_KEY` - Secret for JWT tokens (change in production!)
- `DEBUG` - Enable debug mode (set to `false` in production)

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
