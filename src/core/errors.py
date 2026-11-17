"""Structured application error types with user-friendly messages and recovery advice."""

from __future__ import annotations


class AppError(Exception):
    """Domain error carrying a safe, plain-English message and actionable suggestion."""

    def __init__(
        self,
        code: str,
        user_message: str,
        suggestion: str,
        status_code: int = 400,
    ) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.suggestion = suggestion
        self.status_code = status_code

    def to_dict(self) -> dict[str, str]:
        """Serialize error details safely for API responses and job manifests."""
        return {
            "code": self.code,
            "message": self.user_message,
            "suggestion": self.suggestion,
        }
