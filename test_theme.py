import streamlit as st
import os

if "theme" not in st.session_state:
    st.session_state.theme = "light"

if st.button("Toggle Theme"):
    new_theme = "dark" if st.session_state.theme == "light" else "light"
    st.session_state.theme = new_theme
    
    with open(".streamlit/config.toml", "w") as f:
        if new_theme == "dark":
            f.write('[theme]\nbase="dark"\nprimaryColor="#2563D6"\n')
        else:
            f.write('[theme]\nbase="light"\nprimaryColor="#2563D6"\nbackgroundColor="#F7F9FC"\n')
            
    st.rerun()
    
st.write(f"Current theme: {st.session_state.theme}")
