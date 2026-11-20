"""Clé d'accès unique (variable ACCESS_KEY) devant Dash, /api et /mcp.

La clé est acceptée dans : `?key=...`, l'en-tête `X-API-Key`, `Authorization: Bearer ...` ou le cookie `acces`.
Un navigateur qui ouvre une page avec `?key=...` reçoit le cookie puis est redirigé vers l'URL sans la clé.
Sans ACCESS_KEY, tout reste ouvert (développement local).
"""
import hmac
from http.cookies import SimpleCookie
from urllib.parse import parse_qsl, urlencode

COOKIE = "acces"
DUREE_COOKIE = 30 * 24 * 3600


class CleAcces:
    def __init__(self, app, cle: str | None):
        self.app = app
        self.cle = cle or None

    def _valide(self, candidat) -> bool:
        return bool(candidat) and hmac.compare_digest(candidat.encode(), self.cle.encode())

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket") or self.cle is None:
            return await self.app(scope, receive, send)

        en_tetes = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        params = parse_qsl(scope["query_string"].decode("latin-1"), keep_blank_values=True)
        cle_url = next((v for k, v in params if k == "key"), None)
        bearer = en_tetes.get("authorization", "")
        bearer = bearer[7:] if bearer.lower().startswith("bearer ") else None
        cookie = SimpleCookie(en_tetes.get("cookie", "")).get(COOKIE)

        ok_url = self._valide(cle_url)
        if not (ok_url or self._valide(en_tetes.get("x-api-key")) or self._valide(bearer) or self._valide(cookie and cookie.value)):
            return await self._refuser(scope, receive, send)

        # Navigateur arrivé avec ?key=... : poser le cookie et retirer la clé de l'URL.
        if ok_url and scope["type"] == "http" and scope["method"] == "GET" and "text/html" in en_tetes.get("accept", ""):
            reste = urlencode([(k, v) for k, v in params if k != "key"])
            cible = scope["root_path"] + scope["path"] + (f"?{reste}" if reste else "")
            reponse = [
                (b"location", cible.encode("latin-1")),
                (b"set-cookie", f"{COOKIE}={cle_url}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={DUREE_COOKIE}".encode("latin-1")),
                (b"content-length", b"0"),
            ]
            await send({"type": "http.response.start", "status": 303, "headers": reponse})
            return await send({"type": "http.response.body", "body": b""})

        return await self.app(scope, receive, send)

    async def _refuser(self, scope, receive, send):
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        corps = b'{"detail":"Cle d acces absente ou invalide (parametre ?key=, en-tete X-API-Key ou Authorization: Bearer)."}'
        await send({"type": "http.response.start", "status": 401, "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(corps)).encode()), (b"www-authenticate", b"Bearer"),
        ]})
        await send({"type": "http.response.body", "body": corps})
