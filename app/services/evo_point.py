"""Evo Points service for gamification."""

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.evo_point import EvoPointTransaction, EvoTransactionType
from app.models.project import Project
from app.models.task import EvoReductionType, Task
from app.models.user import User
from app.schemas.evo_point import (
    EvoPointBalanceResponse,
    EvoPointLeaderboardEntry,
    EvoPointLeaderboardResponse,
    EvoPointTransactionResponse,
    TaskCompletionResult,
)

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


class EvoPointService:
    """Service for managing evo points transactions and calculations."""

    def __init__(self, db: Session):
        self.db = db

    def get_user(self, user_id: int) -> User:
        """Get user by ID or raise NotFoundError."""
        user = self.db.get(User, user_id)
        if not user:
            raise NotFoundError(f"User with id {user_id} not found")
        return user

    def get_project_default_evo_points(self, project_id: int) -> int:
        """Get the default evo points setting for a project."""
        project = self.db.get(Project, project_id)
        if not project:
            return 0
        return project.default_evo_points

    def get_effective_evo_points(self, task: Task, project_id: int) -> int:
        """Get the effective evo points for a task (task value or project default)."""
        if task.evo_points is not None:
            return task.evo_points
        return self.get_project_default_evo_points(project_id)

    def calculate_reward_points(
        self,
        task: Task,
        project_id: int,
        completion_time: datetime | None = None,
    ) -> int:
        """
        Calculate the actual reward points for a task based on completion time.
        
        Args:
            task: The task being completed
            project_id: Project ID for fetching defaults
            completion_time: When the task is being completed (defaults to now)
            
        Returns:
            The calculated reward points (may be reduced based on reduction rules)
        """
        if completion_time is None:
            completion_time = datetime.now(IST)
        
        # Ensure completion_time has timezone
        if completion_time.tzinfo is None:
            completion_time = completion_time.replace(tzinfo=IST)
        
        full_points = self.get_effective_evo_points(task, project_id)
        
        # If no due_datetime or no reduction configured, return full points
        if not task.due_datetime or task.evo_reduction_type == EvoReductionType.NONE:
            return full_points
        
        due_datetime = task.due_datetime
        if due_datetime.tzinfo is None:
            due_datetime = due_datetime.replace(tzinfo=IST)
        
        # If completed on time, return full points
        if completion_time <= due_datetime:
            return full_points
        
        # Task is late - apply reduction based on type
        if task.evo_reduction_type == EvoReductionType.GRADUAL:
            return self._calculate_gradual_reduction(
                full_points=full_points,
                due_datetime=due_datetime,
                extension_end=task.evo_extension_end,
                completion_time=completion_time,
            )
        elif task.evo_reduction_type == EvoReductionType.FIXED:
            return self._calculate_fixed_reduction(
                full_points=full_points,
                fixed_points=task.evo_fixed_reduction_points or 0,
                extension_end=task.evo_extension_end,
                completion_time=completion_time,
            )
        
        return full_points

    def _calculate_gradual_reduction(
        self,
        full_points: int,
        due_datetime: datetime,
        extension_end: datetime | None,
        completion_time: datetime,
    ) -> int:
        """
        Calculate points with gradual linear decay.
        
        Points decay linearly from full_points at due_datetime to 0 at extension_end.
        """
        if extension_end is None:
            # No extension configured, return 0 if late
            return 0
        
        if extension_end.tzinfo is None:
            extension_end = extension_end.replace(tzinfo=IST)
        
        # If completed after extension end, no points
        if completion_time >= extension_end:
            return 0
        
        # Linear interpolation
        total_decay_seconds = (extension_end - due_datetime).total_seconds()
        elapsed_seconds = (completion_time - due_datetime).total_seconds()
        
        if total_decay_seconds <= 0:
            return 0
        
        remaining_ratio = 1 - (elapsed_seconds / total_decay_seconds)
        return max(0, int(full_points * remaining_ratio))

    def _calculate_fixed_reduction(
        self,
        full_points: int,
        fixed_points: int,
        extension_end: datetime | None,
        completion_time: datetime,
    ) -> int:
        """
        Calculate points with fixed reduction after due time.
        
        fixed_points is the amount to SUBTRACT from full_points.
        Returns (full_points - fixed_points) if completed between due_datetime and extension_end.
        Returns 0 if completed after extension_end.
        """
        reduced_amount = max(0, full_points - fixed_points)
        
        if extension_end is None:
            # No extension, return reduced points for any late completion
            return reduced_amount
        
        if extension_end.tzinfo is None:
            extension_end = extension_end.replace(tzinfo=IST)
        
        # If completed after extension end, no points
        if completion_time >= extension_end:
            return 0
        
        # Within grace period, return reduced points
        return reduced_amount

    def award_task_points(
        self,
        task: Task,
        user_id: int,
        project_id: int,
        completion_time: datetime | None = None,
    ) -> TaskCompletionResult:
        """
        Award evo points to a user for completing a task.
        
        Args:
            task: The completed task
            user_id: User who completed the task
            project_id: Project ID
            completion_time: When the task was completed
            
        Returns:
            TaskCompletionResult with points earned info
        """
        if completion_time is None:
            completion_time = datetime.now(IST)
        
        # Only user-assigned tasks can earn points
        if task.assigned_to_user_id is None or task.assigned_to_user_id != user_id:
            return TaskCompletionResult(
                task_id=task.id,
                points_earned=None,
                new_balance=None,
            )
        
        effective_points = self.get_effective_evo_points(task, project_id)
        
        # If task has no evo points, skip
        if effective_points <= 0:
            return TaskCompletionResult(
                task_id=task.id,
                points_earned=0,
                new_balance=self.get_user_balance(user_id),
            )
        
        # Calculate actual reward
        actual_points = self.calculate_reward_points(task, project_id, completion_time)
        
        # Check if late
        was_late = False
        if task.due_datetime:
            due_dt = task.due_datetime
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=IST)
            was_late = completion_time > due_dt
        
        # Credit the points
        if actual_points > 0:
            user = self.get_user(user_id)
            new_balance = user.evo_points + actual_points
            user.evo_points = new_balance
            
            # Create transaction record
            metadata = {
                "task_title": task.title,
                "original_points": effective_points,
                "was_late": was_late,
            }
            if was_late:
                metadata["reduction_applied"] = effective_points - actual_points
                metadata["reduction_type"] = task.evo_reduction_type.value
            
            transaction = EvoPointTransaction(
                user_id=user_id,
                project_id=project_id,
                transaction_type=EvoTransactionType.TASK_REWARD,
                amount=actual_points,
                balance_after=new_balance,
                reason=f"Completed task: {task.title}",
                task_id=task.id,
                metadata=metadata,
            )
            self.db.add(transaction)
            self.db.flush()
            
            return TaskCompletionResult(
                task_id=task.id,
                points_earned=actual_points,
                new_balance=new_balance,
                was_late=was_late,
                original_points=effective_points if was_late else None,
                reduction_applied=effective_points - actual_points if was_late else None,
            )
        
        return TaskCompletionResult(
            task_id=task.id,
            points_earned=0,
            new_balance=self.get_user_balance(user_id),
            was_late=was_late,
            original_points=effective_points,
            reduction_applied=effective_points,
        )

    def admin_credit(
        self,
        user_id: int,
        amount: int,
        reason: str,
        performed_by_id: int,
        project_id: int | None = None,
    ) -> EvoPointTransactionResponse:
        """
        Admin credits evo points to a user.
        
        Args:
            user_id: User to credit
            amount: Points to add (must be positive)
            reason: Reason for the credit
            performed_by_id: Admin performing the action
            project_id: Optional project context
            
        Returns:
            Transaction record
        """
        if amount <= 0:
            raise ValidationError("Credit amount must be positive")
        
        user = self.get_user(user_id)
        new_balance = user.evo_points + amount
        user.evo_points = new_balance
        
        transaction = EvoPointTransaction(
            user_id=user_id,
            project_id=project_id,
            transaction_type=EvoTransactionType.ADMIN_CREDIT,
            amount=amount,
            balance_after=new_balance,
            reason=reason,
            performed_by_id=performed_by_id,
        )
        self.db.add(transaction)
        self.db.flush()
        self.db.refresh(transaction)
        
        return self._enrich_transaction(transaction)

    def admin_debit(
        self,
        user_id: int,
        amount: int,
        reason: str,
        performed_by_id: int,
        project_id: int | None = None,
    ) -> EvoPointTransactionResponse:
        """
        Admin debits evo points from a user.
        
        Args:
            user_id: User to debit
            amount: Points to remove (must be positive)
            reason: Reason for the debit
            performed_by_id: Admin performing the action
            project_id: Optional project context
            
        Returns:
            Transaction record
        """
        if amount <= 0:
            raise ValidationError("Debit amount must be positive")
        
        user = self.get_user(user_id)
        new_balance = user.evo_points - amount
        
        # Allow negative balance (configurable in the future)
        user.evo_points = new_balance
        
        transaction = EvoPointTransaction(
            user_id=user_id,
            project_id=project_id,
            transaction_type=EvoTransactionType.ADMIN_DEBIT,
            amount=-amount,  # Store as negative for debit
            balance_after=new_balance,
            reason=reason,
            performed_by_id=performed_by_id,
        )
        self.db.add(transaction)
        self.db.flush()
        self.db.refresh(transaction)
        
        return self._enrich_transaction(transaction)

    def get_user_balance(self, user_id: int) -> int:
        """Get current evo points balance for a user."""
        user = self.db.get(User, user_id)
        if not user:
            return 0
        return user.evo_points

    def get_user_balance_with_transactions(
        self,
        user_id: int,
        project_id: int | None = None,
        limit: int = 10,
    ) -> EvoPointBalanceResponse:
        """Get user's balance with recent transactions."""
        user = self.get_user(user_id)
        
        query = (
            select(EvoPointTransaction)
            .where(EvoPointTransaction.user_id == user_id)
            .order_by(EvoPointTransaction.created_at.desc())
            .limit(limit)
        )
        
        if project_id:
            query = query.where(EvoPointTransaction.project_id == project_id)
        
        result = self.db.execute(query)
        transactions = result.scalars().all()
        
        return EvoPointBalanceResponse(
            user_id=user.id,
            user_name=user.name,
            current_balance=user.evo_points,
            recent_transactions=[
                self._enrich_transaction(t) for t in transactions
            ],
        )

    def get_transactions(
        self,
        project_id: int | None = None,
        user_id: int | None = None,
        transaction_type: EvoTransactionType | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[EvoPointTransactionResponse], int]:
        """Get transactions with filtering."""
        query = select(EvoPointTransaction)
        
        if project_id:
            query = query.where(EvoPointTransaction.project_id == project_id)
        if user_id:
            query = query.where(EvoPointTransaction.user_id == user_id)
        if transaction_type:
            query = query.where(EvoPointTransaction.transaction_type == transaction_type)
        
        # Count total
        count_result = self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0
        
        # Get paginated results
        query = (
            query
            .order_by(EvoPointTransaction.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        result = self.db.execute(query)
        transactions = result.scalars().all()
        
        return [self._enrich_transaction(t) for t in transactions], total

    def get_leaderboard(
        self,
        project_id: int | None = None,
        limit: int = 10,
        current_user_id: int | None = None,
    ) -> EvoPointLeaderboardResponse:
        """Get evo points leaderboard."""
        # Get top users by evo_points
        query = (
            select(User)
            .where(User.is_active == True)
            .order_by(User.evo_points.desc())
            .limit(limit)
        )
        
        result = self.db.execute(query)
        users = result.scalars().all()
        
        entries = [
            EvoPointLeaderboardEntry(
                rank=idx + 1,
                user_id=user.id,
                user_name=user.name,
                evo_points=user.evo_points,
            )
            for idx, user in enumerate(users)
        ]
        
        # Get current user's rank if provided
        current_user_rank = None
        if current_user_id:
            rank_query = select(func.count()).where(
                User.is_active == True,
                User.evo_points > (
                    select(User.evo_points).where(User.id == current_user_id).scalar_subquery()
                )
            )
            rank_result = self.db.execute(rank_query)
            users_above = rank_result.scalar() or 0
            current_user_rank = users_above + 1
        
        return EvoPointLeaderboardResponse(
            entries=entries,
            current_user_rank=current_user_rank,
        )

    def _enrich_transaction(
        self,
        transaction: EvoPointTransaction,
    ) -> EvoPointTransactionResponse:
        """Enrich transaction with related names."""
        return EvoPointTransactionResponse(
            id=transaction.id,
            user_id=transaction.user_id,
            project_id=transaction.project_id,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            balance_after=transaction.balance_after,
            reason=transaction.reason,
            task_id=transaction.task_id,
            performed_by_id=transaction.performed_by_id,
            extra_data=transaction.extra_data,
            created_at=transaction.created_at,
            user_name=transaction.user.name if transaction.user else None,
            performed_by_name=transaction.performed_by.name if transaction.performed_by else None,
            task_title=transaction.task.title if transaction.task else None,
        )
