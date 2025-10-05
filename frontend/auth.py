import streamlit as st
import requests
import time

def signup(fastapi_base_url: str):
    st.subheader("📝 Signup")
    fullname = st.text_input("Full Name", key="signup_fullname")
    email = st.text_input("Email", key="signup_email")
    password = st.text_input("Password", type="password", key="signup_password")

    if st.button("Signup"):
        payload = {"fullname": fullname, "email": email, "password": password}
        try:
            r = requests.post(f"{fastapi_base_url}/signup", json=payload)
            if r.status_code == 200:
                st.success("✅ Signup successful! Please login.")
            else:
                st.error(f"❌ {r.json().get('detail', 'Signup failed')}")
        except Exception as e:
            st.error(f"❌ Connection error: {e}")

def login(fastapi_base_url: str):
    st.subheader("🔑 Login")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login"):
        payload = {"username": email, "password": password}
        try:
            r = requests.post(f"{fastapi_base_url}/login", data=payload) 
            if r.status_code == 200:
                token = r.json()["access_token"]
                st.session_state["access_token"] = token
                st.session_state["is_authenticated"] = True
                st.success("✅ Logged in successfully!")
                st.toast("✅ Logged in successfully!",duration="short")
                st.rerun()
            else:
                st.error(f"❌ {r.json().get('detail', 'Login failed')}")
        except Exception as e:
            st.error(f"❌ Connection error: {e}")

def logout(fastapi_base_url: str):
    try:
        r = requests.post(f"{fastapi_base_url}/logout", cookies={"access_token": st.session_state.get("access_token")})
        if r.status_code == 200:
            st.success("✅ Logged out successfully!")
            st.session_state.clear()
            st.toast("👋 Returning to login...",duration="short")
            st.rerun()
        else:
            st.warning(f"⚠️ Logout failed: {r.json().get('detail', 'Unknown error')}")
    except Exception as e:
        st.error(f"❌ Connection error during logout: {e}")
