"""خطاهای nl_command."""


class NLCommandError(Exception):
    def __init__(self, message: str, code: str = 'error', status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status
