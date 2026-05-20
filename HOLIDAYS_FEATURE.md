# Holidays & User Leaves Feature

## Overview
This feature allows project administrators to manage project-wide holidays and individual user leaves, automatically skipping recurring task generation on marked dates.

## Database Schema

### project_holidays Table
- `id`: Primary key
- `project_id`: Foreign key to projects table
- `holiday_date`: DATE - The holiday date
- `name`: VARCHAR(255) - Optional holiday name
- `description`: TEXT - Optional description
- `created_by_id`: Foreign key to users table
- `created_at`, `updated_at`: Timestamps
- **Unique constraint**: (project_id, holiday_date)
- **Indexes**: project_id, holiday_date

### user_leaves Table
- `id`: Primary key
- `project_id`: Foreign key to projects table
- `user_id`: Foreign key to users table
- `leave_date`: DATE - The leave date
- `reason`: VARCHAR(255) - Optional reason
- `notes`: TEXT - Optional notes
- `created_by_id`: Foreign key to users table
- `created_at`, `updated_at`: Timestamps
- **Unique constraint**: (project_id, user_id, leave_date)
- **Indexes**: project_id, user_id, leave_date, composite (project_id, user_id, leave_date)

## Backend Implementation

### Services (app/services/holiday.py)

#### HolidayService
- `is_holiday(project_id, check_date)` → bool
  - Checks if a date is marked as a holiday
- `cancel_recurring_tasks_for_date(project_id, target_date)` → int
  - Cancels PENDING recurring tasks for a specific date
- `create_holiday(project_id, holiday_data, created_by_id)` → ProjectHolidayResponse
  - Creates a holiday and auto-cancels tasks if date <= today
- `list_holidays(project_id, year?, month?)` → list[ProjectHolidayResponse]
  - Lists holidays with optional year/month filtering
- `delete_holiday(project_id, holiday_id)` → bool
  - Deletes a holiday (does not restore tasks)

#### UserLeaveService
- `is_user_on_leave(project_id, user_id, check_date)` → bool
  - Checks if a user is on leave
- `cancel_user_tasks_for_date(project_id, user_id, target_date)` → int
  - Cancels a user's PENDING recurring tasks for a specific date
- `create_leave(project_id, leave_data, created_by_id)` → UserLeaveResponse
  - Creates a leave and auto-cancels user's tasks if date <= today
- `list_leaves(project_id, user_id?, year?, month?)` → list[UserLeaveResponse]
  - Lists leaves with optional filtering
- `delete_leave(project_id, leave_id)` → bool
  - Deletes a leave (does not restore tasks)

### Scheduler Integration (app/services/recurring_task.py)
The `generate_tasks_for_date()` method has been updated to:
1. Group templates by project_id
2. Check `is_holiday()` for each project - skip entire project if true
3. For each template with `assigned_to_user_id`, check `is_user_on_leave()` - skip if true
4. Role-assigned tasks (assigned_to_role_id) bypass user leave checks

**Schedule**: Runs daily at 00:05 IST (Asia/Kolkata)

### API Endpoints (app/api/v1/endpoints/holidays.py)

#### Holiday Endpoints
- `GET /api/v1/holidays/holidays` - List holidays (project member access)
  - Query params: `year`, `month`
- `POST /api/v1/holidays/holidays` - Create holiday (project admin only)
- `DELETE /api/v1/holidays/holidays/{holiday_id}` - Delete holiday (project admin only)

#### User Leave Endpoints
- `GET /api/v1/holidays/leaves` - List leaves (project member access)
  - Query params: `user_id`, `year`, `month`
- `POST /api/v1/holidays/leaves` - Create leave (project admin only)
- `DELETE /api/v1/holidays/leaves/{leave_id}` - Delete leave (project admin only)

## Frontend Implementation

### API Client (src/lib/holidays-api.ts)
- `getHolidays(params?)` - Fetch holidays
- `createHoliday(payload)` - Create holiday
- `deleteHoliday(holidayId)` - Delete holiday
- `getUserLeaves(params?)` - Fetch user leaves
- `createUserLeave(payload)` - Create leave
- `deleteUserLeave(leaveId)` - Delete leave
- Query keys for React Query caching

### Components

#### HolidayCalendar (src/components/holidays/HolidayCalendar.tsx)
- Calendar interface with highlighted holiday dates
- Click to mark a date as holiday
- Dialog for entering holiday name and description
- Sidebar showing holidays for current month
- Delete holiday functionality
- Success toasts showing tasks cancelled count

#### UserLeaveCalendar (src/components/holidays/UserLeaveCalendar.tsx)
- User list sidebar for selecting a user
- Calendar interface with highlighted leave dates
- Click to mark a date as leave for selected user
- Dialog for entering reason and notes
- Sidebar showing leaves for current user/month
- Delete leave functionality
- Success toasts showing tasks cancelled count

#### Holidays Page (src/app/holidays/page.tsx)
- Main page with Tabs component
- Tab 1: Project Holidays (HolidayCalendar)
- Tab 2: User Leaves (UserLeaveCalendar)
- Information panel explaining important rules
- Protected by MainLayout (requires authentication and project selection)

## Key Features

### Task Cancellation Rules
1. **Past/Today dates**: When marking a date as holiday/leave, if the date is today or in the past, all PENDING recurring tasks for that date are automatically cancelled
2. **Future dates**: Task generation is skipped by the scheduler
3. **Recurring tasks only**: Only tasks where `recurring_template_id IS NOT NULL` are affected
4. **User leaves**: Only affects tasks where `assigned_to_user_id` matches the user on leave
5. **Role-assigned tasks**: Tasks with `assigned_to_role_id` (but no `assigned_to_user_id`) bypass user leave checks

### Permissions
- **Project Admin**: Required for create and delete operations
- **Project Member**: Can view holidays and leaves

### Important Behaviors
- Deleting a holiday/leave does **NOT** restore previously cancelled tasks
- Duplicate prevention: Cannot mark same date twice for same project/user
- Only affects **scheduled recurring tasks**, not manually created tasks

## Migration
Run the migration:
```bash
cd school_ops_sv
uv run alembic upgrade head
```

Migration file: `alembic/versions/67c099db1ca1_add_holiday_and_leave_management.py`

## Testing Checklist
- [ ] Backend starts without errors
- [ ] Holidays API endpoints accessible
- [ ] User leaves API endpoints accessible
- [ ] Scheduler integrates holiday checks correctly
- [ ] Frontend calendar displays holidays
- [ ] Frontend calendar allows creating holidays
- [ ] User leave calendar works with user selection
- [ ] Task cancellation works for past dates
- [ ] Task generation skips future holiday dates
- [ ] Permissions enforced (admin for create/delete)

## Git Commits
All changes committed with conventional commit messages:
- Database: `feat: add project_holidays and user_leaves tables and models`
- Schemas: `feat: add holiday and user leave schemas`
- Services: `feat: add HolidayService and UserLeaveService`
- Scheduler: `feat: integrate holiday and leave checks into recurring task scheduler`
- API: `feat: add holiday and user leave API endpoints`
- Frontend: `feat: add holiday calendar component with API integration`
- Frontend: `feat: add user leave calendar component with user selector`
- Frontend: `feat: add holidays page with tabs for holidays and leaves`
- Fixes: `fix: use ConflictError instead of DuplicateResourceError`

## Future Enhancements
- Bulk holiday import (e.g., CSV upload for annual holidays)
- Recurring holidays (e.g., every first Monday)
- Leave approval workflow
- Calendar export (iCal format)
- Email notifications for upcoming leaves
