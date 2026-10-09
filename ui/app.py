"""Interfaz mínima para usar cualquiera de los servidores de la federación."""

import os
import requests
import streamlit as st

SERVERS = dict(
    item.split("=", 1)
    for item in os.getenv(
        "SERVERS",
        "server-a=http://localhost:8001,server-b=http://localhost:8002,server-c=http://localhost:8003",
    ).split(",")
)

st.set_page_config(page_title="Micropublicaciones", page_icon="💬")
st.session_state.setdefault("sessions", {})

server = st.sidebar.selectbox("Servidor", list(SERVERS))
base = SERVERS[server]
session = st.session_state.sessions.get(server)

def api(method: str, path: str, **kwargs) -> requests.Response:
    headers = {"Authorization": f"Bearer {session['token']}"} if session else {}
    return requests.request(method, f"{base}/api{path}", headers=headers, timeout=5, **kwargs)

def error(resp: requests.Response) -> None:
    detail = resp.json().get("detail",resp.text) if resp.content else resp.status_code
    st.error(detail if isinstance(detail, str) else "Datos no válidos")

def show_notes(notes: list[dict]) -> None:
    if not notes:
        st.caption("No hay publicaciones")
    for note in notes:
        author = note["author"]
        with st.container(border=True):
            st.markdown(f"**{author['display_name']}** `@{author['username']}@{author['domain']}")
            st.write(note["content"])
            st.caption(note["published"][:19].replace("T", " "))

if session is None:
    st.title(f"Micropublicaciones · {server}")
    login_tab, register_tab = st.tabs(["Iniciar sesión", "Registrarse"])
    with login_tab, st.form("login"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            resp = api("POST", "/login", json={"username": username, "password": password})
            if resp.ok:
                st.session_state.sessions[server] = {"token": resp.json()["token"], "username": username}
                st.rerun()
            error(resp)
    with register_tab, st.form("register"):
        username = st.text_input("Usuario (minúsculas, números y _)")
        display_name = st.text_input("Nombre visible")
        password = st.text_input("Contraseña (mín. 6)", type="password")
        if st.form_submit_button("Crear cuenta"):
            body = {"username": username, "password": password, "display_name": display_name}
            resp = api("POST", "/register", json=body)
            if resp.ok:
                st.success("Cuenta creada. Ya puedes iniciar sesión")
            else:
                error(resp)
    st.stop()

me = session["username"]
st.sidebar.markdown(f"Conectando como **@{me}@{server}**")
if st.sidebar.button("Cerrar sesión"):
    del st.session_state.sessions[server]
    st.rerun()

home_tab, users_tab, profile_tab = st.tabs(["Inicio", "Usuarios", "Mi perfil"])

with home_tab:
    with st.form("publish", clear_on_submit=True):
        content = st.text_area("¿Qué está pasando?", max_chars=500)
        if st.form_submit_button("Publicar"):
            resp = api("POST", "/notes", json={"content": content})
            if not resp.ok:
                error(resp)
    show_notes(api("GET","/timelines/home").json())

with users_tab:
    username = st.text_input("Buscar usuario en este servidor")
    if username:
        resp = api("GET", f"/users/{username}")
        if not resp.ok:
            error(resp)
        else:
            user = resp.json()
            st.subheader(f"{user['display_name']} · @{user['username']}@{user['domain']}")
            following = {u["username"] for u in api("GET", f"/users/{me}/following").json()}
            if username != me:
                if username in following:
                    if st.button("Dejar de seguir"):
                        api("DELETE", f"/users/{username}/follow")
                        st.rerun()
                elif st.button("Seguir"):
                    api("POST", f"/users/{username}/follow")
                    st.rerun()
            show_notes(api("GET", f"/users/{username}/notes").json())

with profile_tab:
    following = api("GET", f"/users/{me}/following").json()
    followers = api("GET", f"/users/{me}/followers").json()
    left, right = st.columns(2)
    left.metric("Siguiendo", len(following))
    left.write(", ".join(f"@{u['username']}" for u in following) or "—")
    right.metric("Seguidores", len(followers))
    right.write(", ".join(f"@{u['username']}" for u in followers) or "—")
    st.subheader("Mis publicaciones")
    show_notes(api("GET", f"/users/{me}/notes").json())