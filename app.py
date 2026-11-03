
import streamlit as st

st.set_page_config(
    page_title="AI Documentary Studio",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 AI Documentary Studio")
st.subheader("Your Personal AI Video Creator")

script = st.text_area(
    "अपनी हिंदी वीडियो स्क्रिप्ट यहाँ डालें",
    height=250
)

images = st.selectbox(
    "कितनी Images चाहिए?",
    [80, 90, 100]
)

voice = st.selectbox(
    "AI Voice चुनें",
    ["Hindi Male", "Hindi Female"]
)

quality = st.selectbox(
    "Video Quality",
    ["1080p", "720p"]
)

if st.button("Generate Video"):
    if script.strip():
        st.success("Script successfully received!")
        st.write("Images:", images)
        st.write("Voice:", voice)
        st.write("Quality:", quality)
    else:
        st.warning("पहले Script डालें!")
      
