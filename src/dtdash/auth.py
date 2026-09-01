"""Autenticacao nas APIs da plataforma Dynatrace.

Suporta os dois metodos oficiais de acesso "de fora" do tenant:

* Platform token (``dt0s16.*``) - enviado direto como Bearer;
* OAuth client credentials - troca client_id/secret por um access token no SSO
  (https://sso.dynatrace.com/sso/oauth2/token).
"""

import time

from . import httpclient
from .errors import AuthError


class TokenProvider(object):
    """Fornece o header Authorization para um perfil de tenant."""

    def __init__(self, profile, transport=None, clock=time.time):
        self.profile = profile
        self._transport = transport or httpclient.request
        self._clock = clock
        self._token = None
        self._expires_at = 0.0

    # ------------------------------------------------------------------ api
    def authorization(self):
        return "Bearer %s" % self.access_token()

    def access_token(self):
        if self.profile.auth_method == "platform_token":
            token = self.profile.resolve_platform_token()
            if not token:
                raise AuthError(
                    "platform token nao encontrado (variavel %s)"
                    % self.profile.platform_token_env
                )
            return token
        return self._oauth_token()

    def invalidate(self):
        self._token = None
        self._expires_at = 0.0

    # ---------------------------------------------------------------- oauth
    def _oauth_token(self):
        now = self._clock()
        if self._token and now < self._expires_at - 30:
            return self._token

        client_id = self.profile.resolve_oauth_client_id()
        client_secret = self.profile.resolve_oauth_client_secret()
        if not (client_id and client_secret):
            raise AuthError(
                "credenciais OAuth ausentes (%s / %s)"
                % (self.profile.oauth_client_id_env, self.profile.oauth_client_secret_env)
            )

        form = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": " ".join(self.profile.scopes or []),
        }
        if self.profile.oauth_account_urn:
            form["resource"] = self.profile.oauth_account_urn

        response = self._transport(
            "POST",
            self.profile.sso_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=httpclient.encode_form(form),
            verify=self.profile.verify_tls,
        )
        if not response.ok:
            raise AuthError(
                "falha ao obter token OAuth (HTTP %s): %s"
                % (response.status, (response.text or "")[:500])
            )
        payload = response.json() or {}
        token = payload.get("access_token")
        if not token:
            raise AuthError("resposta do SSO sem access_token")
        self._token = token
        self._expires_at = self._clock() + float(payload.get("expires_in") or 300)
        return token
