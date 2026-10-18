"""Runtime ایزوله دیوار برای هر درخواست — بدون singleton Engine."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from workspace.services.divar_session.pd_import import load_pd_main


@dataclass
class SessionHealth:
    ok: bool
    needs_relogin: bool
    status: str
    expires_at: Optional[datetime] = None


class DivarUserRuntime:
    """یک نشست requests + DivarAuth مستقل."""

    def __init__(self) -> None:
        pd = load_pd_main()
        self._pd = pd
        self.session = requests.Session()
        self.state = pd.DivarSessionState()
        self.http = pd.DivarHTTP(self.session)
        self.auth = pd.DivarAuth(self.http, self.state, self.session)

    def export_session_payload(self, *, phone: str = '') -> dict[str, Any]:
        pd = self._pd
        cookies_by_name: dict[str, dict[str, str]] = {}
        for cookie in self.session.cookies:
            if cookie.name not in pd.SessionStore.AUTH_COOKIE_NAMES and cookie.name not in {
                'city',
                'multi-city',
                'theme',
            }:
                continue
            entry = {
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain or 'divar.ir',
                'path': cookie.path or '/',
            }
            prev = cookies_by_name.get(cookie.name)
            if prev is None or (
                entry['domain'].startswith('.') and not prev['domain'].startswith('.')
            ):
                cookies_by_name[cookie.name] = entry
        session_phone = pd.normalize_phone(phone) if phone else ''
        if not session_phone:
            session_phone = self.auth.get_session_phone() or pd.normalize_phone(self.state.phone or '')
        return {
            'saved_at': datetime.now(timezone.utc).isoformat(),
            'phone': session_phone or None,
            'device_id': self.state.device_id,
            'player_id': self.state.player_id,
            'did': self.state.did,
            'cdid': self.state.cdid,
            'city_slug': self.state.city_slug,
            'cookies': list(cookies_by_name.values()),
        }

    def apply_session_payload(self, data: dict[str, Any]) -> None:
        pd = self._pd
        for key in ('device_id', 'player_id', 'did', 'cdid', 'city_slug'):
            if data.get(key):
                setattr(self.state, key, data[key])
        if data.get('phone'):
            self.state.phone = pd.normalize_phone(str(data['phone']))
        self.session.cookies.clear()
        deduped: dict[str, dict[str, str]] = {}
        for cookie in data.get('cookies') or []:
            if not isinstance(cookie, dict):
                continue
            name = cookie.get('name')
            value = cookie.get('value')
            if not name or value is None:
                continue
            entry = {
                'name': str(name),
                'value': str(value),
                'domain': str(cookie.get('domain') or 'divar.ir'),
                'path': str(cookie.get('path') or '/'),
            }
            prev = deduped.get(entry['name'])
            if prev is None or (
                entry['domain'].startswith('.') and not prev['domain'].startswith('.')
            ):
                deduped[entry['name']] = entry
        for entry in deduped.values():
            pd.set_cookie(
                self.session.cookies,
                entry['name'],
                entry['value'],
                domain=entry['domain'],
                path=entry['path'],
            )

    def export_otp_pending(self, phone: str) -> dict[str, Any]:
        pd = self._pd
        cookies: list[dict[str, str]] = []
        for cookie in self.session.cookies:
            cookies.append({
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain or 'divar.ir',
                'path': cookie.path or '/',
            })
        return {
            'saved_at': datetime.now(timezone.utc).isoformat(),
            'phone': pd.normalize_phone(phone or self.state.phone or ''),
            'pre_auth_session_id': self.state.pre_auth_session_id,
            'device_id': self.state.device_id,
            'player_id': self.state.player_id,
            'did': self.state.did,
            'cdid': self.state.cdid,
            'city_slug': self.state.city_slug,
            'cookies': cookies,
        }

    def apply_otp_pending(self, data: dict[str, Any]) -> None:
        pd = self._pd
        phone = pd.normalize_phone(data.get('phone') or '')
        self.state.pre_auth_session_id = data.get('pre_auth_session_id')
        for key in ('device_id', 'player_id', 'did', 'cdid', 'city_slug'):
            if data.get(key):
                setattr(self.state, key, str(data[key]))
        self.state.phone = phone
        self.session.cookies.clear()
        for raw in data.get('cookies') or []:
            if not isinstance(raw, dict):
                continue
            name = raw.get('name')
            value = raw.get('value')
            if not name or value is None:
                continue
            pd.set_cookie(
                self.session.cookies,
                str(name),
                str(value),
                domain=str(raw.get('domain') or 'divar.ir'),
                path=str(raw.get('path') or '/'),
            )

    def send_login_otp(self, phone: str) -> str:
        self.auth.warmup_session()
        return self.auth.send_login_otp(phone)

    def verify_login_otp(self, otp: str, *, phone: str = '') -> str:
        self.auth.verify_login_otp(otp, phone=phone or None)
        saved = self.auth.get_session_phone() or self._pd.normalize_phone(phone)
        if not saved:
            raise RuntimeError('ورود موفق بود ولی شماره سشن مشخص نشد')
        return saved

    def _jwt_expiry(self, access_token: str) -> Optional[datetime]:
        if not access_token:
            return None
        try:
            parts = access_token.split('.')
            if len(parts) < 2:
                return None
            payload_b64 = parts[1]
            padding = '=' * (-len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
            exp = payload.get('exp')
            if exp is None:
                return None
            return datetime.fromtimestamp(float(exp), tz=timezone.utc)
        except (ValueError, TypeError, json.JSONDecodeError):
            return None

    def health_check(self) -> SessionHealth:
        pd = self._pd
        access = pd.cookie_value(self.session.cookies, 'sAccessToken')
        refresh = pd.cookie_value(self.session.cookies, 'sRefreshToken')
        if not access and not refresh:
            return SessionHealth(ok=False, needs_relogin=True, status='empty')
        if access and pd.jwt_is_expired(access):
            if self.auth.refresh_if_needed():
                access = pd.cookie_value(self.session.cookies, 'sAccessToken')
            else:
                return SessionHealth(
                    ok=False,
                    needs_relogin=True,
                    status='expired',
                    expires_at=self._jwt_expiry(access),
                )
        if not access:
            return SessionHealth(ok=False, needs_relogin=True, status='expired')
        try:
            self.auth.ensure_authenticated()
        except Exception:
            return SessionHealth(
                ok=False,
                needs_relogin=True,
                status='expired',
                expires_at=self._jwt_expiry(access),
            )
        return SessionHealth(
            ok=True,
            needs_relogin=False,
            status='active',
            expires_at=self._jwt_expiry(access),
        )

    def make_scraper(self):
        pd = self._pd
        opts = pd.ScrapeOptions(
            quiet=True,
            browser_hip=False,
            interactive=False,
        )
        return pd.DivarScraper(
            self.http,
            self.auth,
            opts,
            state=self.state,
        )
