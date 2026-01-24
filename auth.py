"""
Simple Authentication Module for Streamlit App

Uses st.secrets for password management (configured in Streamlit Cloud).
"""
import streamlit as st
import hmac


def check_password():
    """
    Returns True if the user has entered a correct password.
    
    For Streamlit Cloud deployment:
    1. Go to your app settings in Streamlit Cloud
    2. Add a secret: password = "your_secure_password"
    
    For local testing:
    1. Create .streamlit/secrets.toml with: password = "test"
    """
    
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password
        else:
            st.session_state["password_correct"] = False

    # First run or password not yet correct
    if st.secrets.get("password") is None:
        # No password configured - allow access (for development)
        return True
    
    if "password_correct" not in st.session_state:
        # First run, show input
        st.text_input(
            "Password", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        st.caption("Enter the password to access the app.")
        return False
    
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input again
        st.text_input(
            "Password", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        st.error("Incorrect password. Please try again.")
        return False
    
    else:
        # Password correct
        return True


def logout():
    """Reset authentication state"""
    if "password_correct" in st.session_state:
        del st.session_state["password_correct"]
