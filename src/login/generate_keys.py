import streamlit_authenticator as stauth

hashed_passwords = stauth.Hasher(['GRUNNVARME123', 'kfpLv3qR']).generate()
print(hashed_passwords)

    