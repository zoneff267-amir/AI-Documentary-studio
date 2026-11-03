
import streamlit as st
import re
import math
import asyncio
import edge_tts
import tempfile
import os

st.set_page_config(
    page_title="AI Documentary Studio",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 AI Documentary Studio")
st.subheader("Your Personal AI Video Creator")

script = st.text_area(
    "अपनी हिंदी वीडियो स्क्रिप्ट यहाँ डालें",
    height=250,
    placeholder="यहाँ पूरी हिंदी स्क्रिप्ट पेस्ट करें..."
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

if st.button("Generate Image Prompts"):
    if not script.strip():
        st.warning("पहले स्क्रिप्ट डालें!")
    else:
        sentences = re.split(r'(?<=[।!?])\s+', script.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        total = len(sentences)
        per_scene = math.ceil(total / images)
        all_prompts = []

        st.success("Scene Planning Complete!")
        st.write("Total Images:", images)

        for i in range(images):
            start = i * per_scene
            end = min(start + per_scene, total)
            scene_text = " ".join(sentences[start:end])

            if not scene_text:
                scene_text = sentences[-1]

            prompt = (
                "Cinematic 2D illustrated documentary scene, "
                "Indian setting, realistic lighting, 16:9 widescreen. "
                "Main character: a 30-year-old Indian man, "
                "heavier build, wearing a sky-blue shirt "
                "and black formal pants. "
                "Keep character design consistent. "
                "No text, no watermark. Scene: " + scene_text
            )

            all_prompts.append(prompt)

            with st.expander("Scene " + str(i + 1)):
                st.write(scene_text)
                st.code(prompt)

        prompts_text = "\n\n".join(
            f"SCENE {i+1}\n{p}"
            for i, p in enumerate(all_prompts)
        )

        st.download_button(
            "📥 Download All Image Prompts",
            prompts_text,
            file_name="all_image_prompts.txt"
        )

st.divider()
st.header("🎙️ Hindi AI Voice Generator")

if st.button("Generate Hindi Voice"):
    if not script.strip():
        st.warning("पहले अपनी स्क्रिप्ट डालें!")
    else:
        try:
            with st.spinner("आपकी हिंदी आवाज़ तैयार हो रही है..."):
                selected_voice = (
                    "hi-IN-MadhurNeural"
                    if voice == "Hindi Male"
                    else "hi-IN-SwaraNeural"
                )

                async def create_voice(path):
                    communicate = edge_tts.Communicate(
                        script,
                        selected_voice
                    )
                    await communicate.save(path)

                with tempfile.NamedTemporaryFile(
                    suffix=".mp3",
                    delete=False
                ) as audio_file:
                    audio_path = audio_file.name

                asyncio.run(create_voice(audio_path))

                with open(audio_path, "rb") as f:
                    audio_bytes = f.read()

                os.remove(audio_path)

                st.success("आपकी AI Voice तैयार है!")
                st.audio(audio_bytes, format="audio/mp3")

                st.download_button(
                    "📥 Download Hindi Voice MP3",
                    audio_bytes,
                    file_name="hindi_voice.mp3",
                    mime="audio/mpeg"
                )

        except Exception as e:
            st.error("Voice बनाने में समस्या आई। इंटरनेट जाँचें और दोबारा कोशिश करें।")
            st.caption(str(e))
            
