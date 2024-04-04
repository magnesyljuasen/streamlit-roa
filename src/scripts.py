import streamlit as st
import streamlit_authenticator as stauth
import yaml
import base64
from PIL import Image
from streamlit_extras.switch_page_button import switch_page
from streamlit_extras.no_default_selectbox import selectbox
from streamlit_extras.add_vertical_space import add_vertical_space

def streamlit_settings():
    st.set_page_config(page_title="Kolbotn", layout="wide", page_icon="src/data/img/AsplanViak_Favicon_32x32.png", initial_sidebar_state="expanded")
    with open("src/styles/main.css") as f:
        st.markdown("<style>{}</style>".format(f.read()), unsafe_allow_html=True)
        #st.markdown("""<style>[data-testid="collapsedControl"] {display: none}</style>""", unsafe_allow_html=True) # ingen sidebar
        #st.markdown("""<style>div[data-testid="stSidebarNav"] {display: none;}</style>""", unsafe_allow_html=True) # litt av sidebar
        st.markdown('''<style>button[title="View fullscreen"]{visibility: hidden;}</style>''', unsafe_allow_html=True) # hide fullscreen
        #st.markdown("""<style>.block-container {padding-top: 1rem;padding-bottom: 0rem;padding-left: 5rem;padding-right: 5rem;}</style>""", unsafe_allow_html=True)

def login():
    with open('src/login/config.yaml') as file:
        config = yaml.load(file, Loader=stauth.SafeLoader)
        authenticator = stauth.Authenticate(config['credentials'],config['cookie']['name'],config['cookie']['key'],config['cookie']['expiry_days'])
        name, authentication_status, username = authenticator.login('Innlogging', 'main')
    return name, authentication_status, username, authenticator

def switch_pages(previous_page_destination, previous_page_text, next_page_destination, next_page_text):
    #add_vertical_space(5)
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button(previous_page_text):
            switch_page(previous_page_destination)
    with c2:
        if st.button(next_page_destination):
            switch_page(next_page_text)

def toggle_closed_expander(state):
    st.session_state[state] = False
    st.session_state.check = True