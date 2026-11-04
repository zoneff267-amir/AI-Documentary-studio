
import streamlit as st
import re
import os
import io
import math
import asyncio
import tempfile
import subprocess
import edge_tts

from pydub import AudioSegment, effects

st.set_page_config(
    page_title="AI Documentary Studio",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 AI Documentary Studio")
st.write("अपनी Script, Images और Hindi AI Voice से Documentary Video बनाएँ।")

# Session state
if "voice_audio_bytes" not in st.session_state:
    st.session_state.voice_audio_bytes = None

if "all_prompts" not in st.session_state:
    st.session_state.all_prompts = []

# Script
st.header("📝 Documentary Script")
script = st.text_area(
    "अपनी पूरी Hindi Script यहाँ डालें",
    height=220,
    placeholder="अपनी Documentary Script यहाँ लिखें..."
)

# Settings
st.header("⚙️ Video Settings")

col1, col2 = st.columns(2)

with col1:
    voice = st.selectbox(
        "AI Voice चुनें",
        ["Hindi Male", "Hindi Female"]
    )

with col2:
    quality = st.selectbox(
        "Video Quality",
        ["1080p", "720p"]
    )

image_count = st.selectbox(
    "कुल Images",
    [80, 90, 100]
)

# Image prompts
st.header("🖼️ Image Prompt Generator")

if st.button("Generate Image Prompts"):
    if not script.strip():
        st.warning("पहले Script डालें।")
    else:
        sentences = [
            x.strip()
            for x in re.split(r"(?<=[।.!?])\s+|\n+", script)
            if x.strip()
        ]

        prompts = []

        for i, sentence in enumerate(sentences):
            prompt = (
                f"Scene {i+1}: {sentence}\n\n"
                "Create a cinematic 2D illustrated finance documentary image. "
                "Indian setting, professional documentary composition, "
                "dramatic realistic lighting, widescreen 16:9. "
                "Keep the recurring character consistent: "
                "30-year-old Indian gentleman, heavier build, "
                "sky-blue shirt and black formal pants. "
                "No text, no watermark."
            )
            prompts.append(prompt)

        st.session_state.all_prompts = prompts
        st.success(f"{len(prompts)} Image Prompts तैयार हैं।")

if st.session_state.all_prompts:
    prompt_text = "\n\n".join(st.session_state.all_prompts)

    st.download_button(
        "📥 Download All Image Prompts",
        prompt_text,
        file_name="all_image_prompts.txt",
        mime="text/plain"
    )

    with st.expander("Image Prompts देखें"):
        for i, prompt in enumerate(st.session_state.all_prompts):
            st.write(f"**Scene {i+1}**")
            st.write(prompt)

# Voice generator
st.divider()
st.header("🎙️ Hindi AI Voice Generator")

if st.button("Generate Enhanced Hindi Voice"):
    if not script.strip():
        st.warning("पहले Script डालें।")
    else:
        try:
            selected_voice = (
                "hi-IN-MadhurNeural"
                if voice == "Hindi Male"
                else "hi-IN-SwaraNeural"
            )

            sentences = [
                x.strip()
                for x in re.split(r"(?<=[।.!?])\s+|\n+", script)
                if x.strip()
            ]

            chunks = []
            current = ""

            for sentence in sentences:
                if len(current) + len(sentence) < 1800:
                    current += sentence + " "
                else:
                    if current.strip():
                        chunks.append(current.strip())
                    current = sentence + " "

            if current.strip():
                chunks.append(current.strip())

            with st.spinner("Hindi AI Voice तैयार हो रही है..."):
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
                        part = AudioSegment.from_mp3(path)
                        final_audio += part
                        final_audio += AudioSegment.silent(
                            duration=120
                        )

                    final_audio = effects.normalize(
                        final_audio,
                        headroom=1.0
                    )

                    output_path = os.path.join(
                        temp_dir, "hindi_voice.mp3"
                    )

                    final_audio.export(
                        output_path,
                        format="mp3",
                        bitrate="192k"
                    )

                    with open(output_path, "rb") as f:
                        audio_bytes = f.read()

            st.session_state.voice_audio_bytes = audio_bytes

            st.success("आपकी Hindi AI Voice तैयार है!")
            st.audio(audio_bytes, format="audio/mp3")

            st.download_button(
                "📥 Download Hindi Voice MP3",
                audio_bytes,
                file_name="enhanced_hindi_voice.mp3",
                mime="audio/mpeg"
            )

        except Exception as e:
            st.error("Voice बनाने में समस्या आई।")
            st.code(str(e))

# Automatic video editor
st.divider()
st.header("🎬 Automatic Video Editor")

st.write(
    "अपनी Gemini से बनाई हुई Images अपलोड करें। "
    "तैयार Hindi AI Voice अपने आप Video में जुड़ जाएगी।"
)

uploaded_images = st.file_uploader(
    "अपनी Documentary Images अपलोड करें",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True
)

if uploaded_images:
    st.success(f"आपने {len(uploaded_images)} Images अपलोड की हैं।")

if st.session_state.voice_audio_bytes:
    st.success("Hindi AI Voice तैयार है।")
else:
    st.info("पहले Hindi AI Voice तैयार करें।")

if st.button("🎬 Create Documentary Video"):

    if not uploaded_images:
        st.error("पहले Images अपलोड करें।")

    elif len(uploaded_images) < 2:
        st.error("कम से कम 2 Images अपलोड करें।")

    elif not st.session_state.voice_audio_bytes:
        st.error("पहले Hindi AI Voice तैयार करें।")

    else:
        try:
            with st.spinner(
                "आपकी Documentary Video बन रही है। कृपया प्रतीक्षा करें..."
            ):

                with tempfile.TemporaryDirectory() as temp_dir:

                    # Save audio
                    audio_path = os.path.join(
                        temp_dir, "voice.mp3"
                    )

                    audio_bytes = st.session_state.voice_audio_bytes

                    with open(audio_path, "wb") as f:
                        f.write(audio_bytes)

                    audio_duration = AudioSegment.from_file(
                        io.BytesIO(audio_bytes),
                        format="mp3"
                    ).duration_seconds

                    # Save uploaded images in upload order
                    image_paths = []

                    for i, img in enumerate(uploaded_images):
                        ext = os.path.splitext(img.name)[1].lower()

                        if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
                            ext = ".png"

                        path = os.path.join(
                            temp_dir, f"scene_{i:04d}{ext}"
                        )

                        with open(path, "wb") as f:
                            f.write(img.getvalue())

                        image_paths.append(path)

                    # Video settings
                    if quality == "1080p":
                        width, height = 1920, 1080
                    else:
                        width, height = 1280, 720

                    fps = 24
                    scene_duration = audio_duration / len(image_paths)
                    frames = max(
                        1,
                        math.ceil(scene_duration * fps)
                    )

                    # FFmpeg command
                    command = ["ffmpeg", "-y"]

                    for path in image_paths:
                        command += [
                            "-loop", "1",
                            "-framerate", str(fps),
                            "-i", path
                        ]

                    command += ["-i", audio_path]

                    filters = []

                    for i in range(len(image_paths)):
                        filters.append(
                            f"[{i}:v]"
                            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                            f"crop={width}:{height},"
                            f"zoompan=z='min(zoom+0.0005,1.08)':"
                            f"x='iw/2-(iw/zoom/2)':"
                            f"y='ih/2-(ih/zoom/2)':"
                            f"d={frames}:s={width}x{height}:fps={fps},"
                            f"setsar=1,format=yuv420p[v{i}]"
                        )

                    video_inputs = "".join(
                        f"[v{i}]"
                        for i in range(len(image_paths))
                    )

                    filters.append(
                        f"{video_inputs}"
                        f"concat=n={len(image_paths)}:v=1:a=0[outv]"
                    )

                    output_path = os.path.join(
                        temp_dir, "documentary.mp4"
                    )

                    command += [
                        "-filter_complex_threads", "1",
                        "-filter_complex", ";".join(filters),
                        "-map", "[outv]",
                        "-map", f"{len(image_paths)}:a:0",
                        "-c:v", "libx264",
                        "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac",
                        "-b:a", "128k",
                        "-t", str(audio_duration),
                        "-shortest",
                        "-movflags", "+faststart",
                        output_path
                    ]

                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=900
                    )

                    if result.returncode != 0:
                        raise Exception(result.stderr[-4000:])

                    if not os.path.exists(output_path):
                        raise Exception("Video file नहीं बनी।")

                    with open(output_path, "rb") as f:
                        video_bytes = f.read()

                    st.success("आपकी Documentary Video तैयार है!")
                    st.video(video_bytes)

                    st.download_button(
                        "📥 Download Documentary MP4",
                        video_bytes,
                        file_name="my_documentary.mp4",
                        mime="video/mp4"
                    )

        except subprocess.TimeoutExpired:
            st.error(
                "वीडियो बनाने में बहुत समय लगा। "
                "कम Images या 720p Quality के साथ फिर कोशिश करें।"
            )

        except Exception as e:
            st.error("वीडियो बनाने में समस्या आई।")
            st.code(str(e))

st.divider()
st.caption(
    "AI Documentary Studio | No Background Music | Hindi AI Voice"
)
