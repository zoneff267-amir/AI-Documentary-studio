
import streamlit as st
import re
import math
import asyncio
import edge_tts
import tempfile
import os
import io
from pydub import AudioSegment, effects
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

if st.button("Generate Enhanced Hindi Voice"):
    if not script.strip():
        st.warning("पहले अपनी स्क्रिप्ट डालें।")
    else:
        try:
            selected_voice = (
                "hi-IN-MadhurNeural"
                if voice == "Hindi Male"
                else "hi-IN-SwaraNeural"
            )

            # Script ko chhote sentences mein baantna
            sentences = re.split(r'(?<=[।.!?])\s+|\n+', script.strip())

            chunks = []
            current_chunk = ""

            for sentence in sentences:
                if len(current_chunk) + len(sentence) < 1800:
                    current_chunk += sentence + " "
                else:
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + " "

            if current_chunk.strip():
                chunks.append(current_chunk.strip())

            with st.spinner("आपकी Smooth AI Voice तैयार हो रही है..."):
                with tempfile.TemporaryDirectory() as temp_dir:

                    async def create_chunks():
                        for i, chunk in enumerate(chunks):
                            path = os.path.join(
                                temp_dir, f"part_{i}.mp3"
                            )
                            communicate = edge_tts.Communicate(
                                chunk, selected_voice
                            )
                            await communicate.save(path)

                    asyncio.run(create_chunks())

                    final_audio = AudioSegment.empty()

                    for i in range(len(chunks)):
                        path = os.path.join(
                            temp_dir, f"part_{i}.mp3"
                        )
                        audio_part = AudioSegment.from_mp3(path)
                        final_audio += audio_part
                        final_audio += AudioSegment.silent(
                            duration=120
                        )

                    # Volume ko balanced karna
                    final_audio = effects.normalize(
                        final_audio, headroom=1.0
                    )

                    output_path = os.path.join(
                        temp_dir, "enhanced_voice.mp3"
                    )

                    final_audio.export(
                        output_path,
                        format="mp3",
                        bitrate="192k"
                    )

                    with open(output_path, "rb") as f:
                        audio_bytes = f.read()
            st.session_state["voice_audio_bytes"] = audio_bytes
            st.success("आपकी Enhanced Hindi Voice तैयार है!")
            st.audio(audio_bytes, format="audio/mp3")

            st.download_button(
                "📥 Download Enhanced Voice MP3",
                audio_bytes,
                file_name="enhanced_hindi_voice.mp3",
                mime="audio/mpeg"
            )

        except Exception as e:
            st.error("Voice बनाने में समस्या आई।")
            st.caption(str(e))
