class JobBudgetExceeded(Exception):
    """Raised when a worker job exceeds token, cost, or tool-call limits."""
