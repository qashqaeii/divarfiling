"""خطاهای سرویس نشست دیوار."""


class DivarSessionError(Exception):
    def __init__(self, message: str, *, code: str = 'divar_error'):
        self.message = message
        self.code = code
        super().__init__(message)


class DivarRateLimited(DivarSessionError):
    def __init__(self):
        super().__init__(
            'درخواست‌های پیاپی — چند ثانیه صبر کنید.',
            code='rate_limited',
        )
