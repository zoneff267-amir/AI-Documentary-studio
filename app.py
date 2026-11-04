
import streamlit as st
import re
import math
import asyncio
import edge_tts
import tempfile
import os
import io
from pydub import AudioSegment, effects
import subprocess
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
    ["1080p", "720p"])
uploaded_images = st.file_uploader(
    "📸 अपनी सभी Documentary Images अपलोड करें",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True
)

if uploaded_images:
    st.success(f"आपने {len(uploaded_images)} Images अपलोड की हैं।")

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
st.divider()
st.header("🎬 Automatic Video Editor")

st.write("अपनी Images और तैयार Hindi AI Voice से वीडियो बनाएँ।")

if uploaded_images:
    st.write(f"Uploaded Images: {len(uploaded_images)}")
else:
    st.info("पहले अपनी Documentary Images अपलोड करें।")

if "voice_audio_bytes" in st.session_state:
    st.success("Hindi AI Voice तैयार है।")
else:
    st.warning("पहले Generate Enhanced Hindi Voice बटन से Voice बनाएँ।")
if st.button("🎬 Create Documentary Video"):
    if not uploaded_images:
        st.error("पहले Images अपलोड करें।")

    elif "voice_audio_bytes" not in st.session_state:
        st.error("पहले Hindi AI Voice तैयार करें।")

    elif len(uploaded_images) < 2:
        st.error("कम से कम 2 Images अपलोड करें।")

    else:
            try:
                with st.spinner("आपका Documentary Video बन रहा है..."):
                    with tempfile.TemporaryDirectory() as temp_dir:

                        audio_bytes = st.session_state["voice_audio_bytes"]
                        audio_path = os.path.join(temp_dir, "voice.mp3")

                        with open(audio_path, "wb") as f:
                            f.write(audio_bytes)

                        audio_duration = AudioSegment.from_file(
                            io.BytesIO(audio_bytes)
                        ).duration_seconds

                        sorted_images = sorted(
                            uploaded_images,
                            key=lambda f: [
                                int(x) if x.isdigit() else x.lower()
                                for x in re.split(r"(\d+)", f.name)
                            ]
                        )

                        image_paths = []

                        for i, img in enumerate(sorted_images):
                            ext = os.path.splitext(img.name)[1].lower()
                            path = os.path.join(
                                temp_dir, f"scene_{i:04d}{ext}"
                            )
                            with open(path, "wb") as f:
                                f.write(img.getvalue())
                            image_paths.append(path)

                        width, height = (
                            (1920, 1080) if quality == "1080p"
                            else (1280, 720)
                        )

                        fps = 24
                        scene_duration = audio_duration / len(image_paths)
                        frames = max(1, round(scene_duration * fps))

                        command = ["ffmpeg", "-y"]

                        

                transition = 0.5
                filters = []

                for i in range(len(image_paths)):
                    command += [
        "-loop", "1",
        "-framerate", str(fps),
        "-t", str(scene_duration),
        "-i", image_paths[i]
                        ]
                    filters.append(
                        f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                        f"crop={width}:{height},"
                        f"zoompan=z='min(zoom+0.0005,1.08)':"
                        f"x='iw/2-(iw/zoom/2)':"
                        f"y='ih/2-(ih/zoom/2)':"
                        f"d=1:s={width}x{height}:fps={fps},"
                        f"setsar=1,format=yuv420p,settb=AVTB,"
                        f"setpts=PTS-STARTPTS[v{i}]"
                    )

                previous = "[v0]"

                for i in range(1, len(image_paths)):
                    output = f"[xf{i}]"
                    offset = scene_duration * i - transition * i

                    filters.append(
                        f"{previous}[v{i}]"
                        f"xfade=transition=fade:"
                        f"duration={transition}:"
                        f"offset={offset:.3f}{output}"
                    )

                    previous = output

                filters.append(f"{previous}format=yuv420p[out]")
                command += [
                            "-i", audio_path,
                            "-filter_complex", ";".join(filters),
                            "-map", "[vout]",
                            "-map", f"{len(image_paths)}:a",
                            "-c:v", "libx264",
                            "-preset", "ultrafast",
                            "-pix_fmt", "yuv420p",
                            "-c:a", "aac",
                            "-b:a", "192k",
                            "-shortest",
                            "-movflags", "+faststart",
                            os.path.join(temp_dir, "documentary.mp4")
                           ]

                result = subprocess.run(
                            command,
                            capture_output=True,
                            text=True,
                            timeout=900
                        )

                if result.returncode != 0:
                        raise Exception(result.stderr[-2000:])

                video_path = os.path.join(
                            temp_dir, "documentary.mp4"
                        )

                with open(video_path, "rb") as f:
                        video_bytes = f.read()

                st.success("आपका Documentary Video तैयार है!")
                st.video(video_bytes)

                st.download_button(
                    "📥 Download  Documentary MP4",
                    video_bytes,
                    file_name="my_documentary.mp4",
                    mime="video/mp4"
                )

            except Exception as e:
                st.error("वीडियो बनाने में समस्या आई।")
                st.caption(str(e))
