#!/usr/bin/env python3
"""Comprueba con la API de administración que el realm importado tiene lo que SmartMentor necesita.

Uso (contra un Keycloak desechable donde ya se importó el realm; lo arma check-realm-import.sh):
    python3 -I keycloak/scripts/verify-realm.py URL USUARIO_ADMIN CONTRASEÑA_ADMIN [--functional]

Siempre verifica la configuración: roles, rol por defecto, autorregistro con correo verificado, fuerza bruta,
política de contraseñas, clientes y sus audiencias, flujo con OTP por rol, sustitución de los marcadores
${VARIABLE} (sin marcadores literales), llaves de firma generadas y ausencia de usuarios.
Con --functional crea usuarios de prueba y comprueba el comportamiento: el aprendiz entra sin OTP y quien tenga
instructor o admin queda obligado a configurar el OTP. Solo usa la biblioteca estándar.
"""

import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REALM = "smartmentor"
TEST_PASSWORD = "Test-only-Passw0rd-123"  # noqa: S105 - valor desechable de un Keycloak efímero
FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    print(("OK    " if condition else "FALLA ") + message)
    if not condition:
        FAILURES.append(message)


class Admin:
    def __init__(self, base: str, user: str, password: str) -> None:
        self.base = base.rstrip("/")
        body = urllib.parse.urlencode(
            {"client_id": "admin-cli", "username": user, "password": password, "grant_type": "password"}
        ).encode()
        url = f"{self.base}/realms/master/protocol/openid-connect/token"
        self.token = json.load(urllib.request.urlopen(url, body))["access_token"]  # noqa: S310

    def call(self, method: str, path: str, body: object = None) -> object:
        request = urllib.request.Request(  # noqa: S310
            f"{self.base}/admin/realms/{REALM}{path}",
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        raw = urllib.request.urlopen(request).read()  # noqa: S310
        return json.loads(raw) if raw else None

    def get(self, path: str) -> object:
        return self.call("GET", path)


def verify_configuration(kc: Admin) -> None:
    realm = kc.get("")
    check(realm["registrationAllowed"] is True, "autorregistro habilitado")
    check(realm["verifyEmail"] is True, "correo verificado obligatorio (verifyEmail)")
    check(realm["bruteForceProtected"] is True, "protección de fuerza bruta")
    check("length(" in (realm.get("passwordPolicy") or ""), "política de contraseñas con longitud mínima")
    check(realm["browserFlow"] == "browser-role-otp", "flujo de login con OTP por rol")
    smtp = realm["smtpServer"]
    check(bool(smtp.get("host")) and "${" not in json.dumps(smtp), "correo (SMTP) con las variables ya sustituidas")

    roles = {r["name"] for r in kc.get("/roles")}
    check({"learner", "instructor", "admin"} <= roles, "roles learner, instructor y admin")
    check(not ({"student", "teacher"} & roles), "sin los roles antiguos student y teacher")
    default_roles = {r["name"] for r in kc.get("/roles/default-roles-smartmentor/composites")}
    check("learner" in default_roles, "learner es parte del rol por defecto")

    clients = {c["clientId"]: c for c in kc.get("/clients")}
    for name in ("smartmentor-ui", "smartmentor-ai", "smartmentor-api-service", "smartmentor-api"):
        check(name in clients, f"existe el cliente {name}")

    def audiences(client: dict) -> set[str]:
        return {m["config"].get("included.client.audience") for m in client.get("protocolMappers", [])}

    ui = clients["smartmentor-ui"]
    check(not ui["publicClient"] and ui["standardFlowEnabled"], "smartmentor-ui es confidencial con flujo estándar")
    check(ui["redirectUris"] == ["http://localhost:8501/oauth2callback"], "smartmentor-ui: URI de retorno de Streamlit")
    check("smartmentor-api" in audiences(ui), "smartmentor-ui: audiencia smartmentor-api")
    service = clients["smartmentor-api-service"]
    check(service["serviceAccountsEnabled"] and not service["standardFlowEnabled"], "api-service: cuenta de servicio")
    check("smartmentor-ai" in audiences(service), "api-service: audiencia smartmentor-ai")
    check(clients["smartmentor-ai"]["bearerOnly"], "smartmentor-ai solo define la audiencia")
    all_uris = [uri for c in clients.values() for uri in c.get("redirectUris", [])]
    check(not any("8081" in uri for uri in all_uris), "ya no existe la URI http://localhost:8081/*")
    for name in ("smartmentor-ui", "smartmentor-api-service"):
        secret = kc.get(f"/clients/{clients[name]['id']}/client-secret").get("value", "")
        check(bool(secret) and not secret.startswith("${"), f"{name}: secreto sustituido desde el entorno")

    expected = {
        "browser-role-otp instructor": {("instructor", "false")},
        "browser-role-otp admin": {("admin", "false"), ("instructor", "true")},
    }
    for flow, conditions in expected.items():
        found = set()
        for execution in kc.get("/authentication/flows/" + urllib.parse.quote(flow) + "/executions"):
            if execution.get("authenticationConfig"):
                config = kc.get("/authentication/config/" + execution["authenticationConfig"])["config"]
                found.add((config["condUserRole"], config["negate"]))
        check(found == conditions, f"flujo «{flow}»: condiciones de rol {sorted(found)}")

    keys = kc.get("/keys")["keys"]
    check(any(k["type"] == "RSA" and k["status"] == "ACTIVE" for k in keys), "llaves RSA de firma generadas al importar")
    check(kc.get("/users") == [], "el realm no trae usuarios")


class Browser:
    """Navegador mínimo: guarda las cookies a mano (cookielib descarta las de «localhost»)."""

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args: object, **kwargs: object) -> None:
            return None

    def __init__(self) -> None:
        self.cookies: dict[str, str] = {}
        self.opener = urllib.request.build_opener(self._NoRedirect)

    def open(self, url: str, data: dict | None = None) -> tuple[int, str, str]:
        request = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None)  # noqa: S310
        if self.cookies:
            request.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in self.cookies.items()))
        try:
            response = self.opener.open(request)
        except urllib.error.HTTPError as error:
            response = error
        for header in response.headers.get_all("Set-Cookie") or []:
            key, _, value = header.split(";")[0].partition("=")
            self.cookies[key] = value
        return response.status if hasattr(response, "status") else response.code, response.headers.get("Location", ""), response.read().decode()


def login_result(base: str, email: str) -> str:
    query = urllib.parse.urlencode(
        {"client_id": "smartmentor-ui", "response_type": "code", "scope": "openid",
         "redirect_uri": "http://localhost:8501/oauth2callback"}
    )
    browser = Browser()
    _, _, page = browser.open(f"{base}/realms/{REALM}/protocol/openid-connect/auth?{query}")
    action = urllib.parse.urljoin(base, html.unescape(re.search(r'action="([^"]+)"', page).group(1)))
    _, location, _ = browser.open(action, {"username": email, "password": TEST_PASSWORD})
    if "CONFIGURE_TOTP" in location:
        return "otp"
    if location.startswith("http://localhost:8501/oauth2callback") and "code=" in location:
        return "sin-otp"
    return f"inesperado: {location[:80]}"


def verify_behavior(kc: Admin, base: str) -> None:
    cases = {"learner": ("sin-otp", ["learner"]), "instructor": ("otp", ["instructor"]),
             "admin": ("otp", ["admin"]), "ambos": ("otp", ["instructor", "admin"])}
    created = []
    try:
        for name, (_, roles) in cases.items():
            email = f"verify-{name}@test.invalid"
            kc.call("POST", "/users", {"username": email, "email": email, "firstName": name, "lastName": "Prueba",
                                       "enabled": True, "emailVerified": True,
                                       "credentials": [{"type": "password", "value": TEST_PASSWORD, "temporary": False}]})
            user_id = kc.get(f"/users?username={email}&exact=true")[0]["id"]
            created.append(user_id)
            kc.call("POST", f"/users/{user_id}/role-mappings/realm", [kc.get(f"/roles/{r}") for r in roles])
        for name, (expected, _) in cases.items():
            result = login_result(base, f"verify-{name}@test.invalid")
            check(result == expected, f"login con rol {name}: {result} (esperado {expected})")

        query = urllib.parse.urlencode({"client_id": "smartmentor-ui", "response_type": "code", "scope": "openid",
                                        "redirect_uri": "http://localhost:8501/oauth2callback"})
        _, _, page = Browser().open(f"{base}/realms/{REALM}/protocol/openid-connect/registrations?{query}")
        check('name="email"' in page and 'name="firstName"' in page, "la pantalla de registro existe")
    finally:
        for user_id in created:
            kc.call("DELETE", f"/users/{user_id}")


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 3:
        print(__doc__)
        return 2
    base = args[0].rstrip("/")
    kc = Admin(base, args[1], args[2])
    verify_configuration(kc)
    if "--functional" in argv:
        verify_behavior(kc, base)
    print(f"\n{len(FAILURES)} comprobaciones fallidas" if FAILURES else "\nRealm correcto")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
