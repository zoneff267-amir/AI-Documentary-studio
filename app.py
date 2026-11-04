import streamlit as st
import re
import os
import io
import tempfile
import subprocess
import asyncio
import edge_tts

from pydub import AudioSegment, effects

st.set_page_config(
    page_title="AI Documentary Studio",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 AI Documentary Studio")

if "voice_audio_bytes" not in st.session_state:
    st.session_state.voice_audio_bytes = None

if "all_prompts" not in st.session_state:
    st.session_state.all_prompts = []


# SCRIPT SETTINGS
st.header("📝 Documentary Script")

script = st.text_area(
    "अपनी पूरी हिंदी स्क्रिप्ट यहाँ डालें",
    height=220
)

scene_count = st.selectbox(
    "कितने Image Prompts चाहिए?",
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


# IMAGE PROMPTS
st.divider()
st.header("🖼️ Image Prompt Generator")

if st.button("Generate Image Prompts"):

    if not script.strip():
        st.warning("पहले अपनी स्क्रिप्ट डालें।")

    else:
        sentences = re.split(
            r'(?<=[।.!?])\s+|\n+',
            script.strip()
        )

        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            st.warning("स्क्रिप्ट में वाक्य नहीं मिले।")

        else:
            prompts = []

            for i in range(scene_count):

                sentence_index = min(
                    int(i * len(sentences) / scene_count),
                    len(sentences) - 1
                )

                scene_text = sentences[sentence_index]

                prompt = f"""
Create a cinematic 2D illustrated documentary image.

Scene {i + 1}:
{scene_text}

Visual style:
Professional finance documentary illustration,
Indian environment, cinematic composition,
dramatic natural lighting, detailed background,
16:9 widescreen composition.

Recurring main character:
A 30-year-old Indian gentleman,
heavier build, wearing a sky-blue shirt
and black formal pants.

Keep the character consistent whenever he appears.
No text, no captions, no watermark.
"""

                prompts.append(prompt.strip())

            st.session_state.all_prompts = prompts
            st.success(f"{len(prompts)} Image Prompts तैयार हैं।")


if st.session_state.all_prompts:

    for i, prompt in enumerate(st.session_state.all_prompts):
        with st.expander(f"Scene {i + 1}"):
            st.write(prompt)

    prompt_text = "\n\n".join(
        f"SCENE {i + 1}\n{p}"
        for i, p in enumerate(st.session_state.all_prompts)
    )

    st.download_button(
        "📥 Download All Image Prompts",
        data=prompt_text,
        file_name="all_image_prompts.txt",
        mime="text/plain"
    )


# HINDI AI VOICE
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

            sentences = re.split(
                r'(?<=[।.!?])\s+|\n+',
                script.strip()
            )

            sentences = [s.strip() for s in sentences if s.strip()]

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

            with st.spinner("Hindi AI Voice तैयार हो रही है..."):

                with tempfile.TemporaryDirectory() as temp_dir:

                    async def create_chunks():

                        for i, chunk in enumerate(chunks):

                            path = os.path.join(
                                temp_dir,
                                f"part_{i}.mp3"
                            )

                            communicate = edge_tts.Communicate(
                                chunk,
                                selected_voice
                            )

                            await communicate.save(path)

                    asyncio.run(create_chunks())

                    final_audio = AudioSegment.empty()

                    for i in range(len(chunks)):

                        path = os.path.join(
                            temp_dir,
                            f"part_{i}.mp3"
                        )

                        audio_part = AudioSegment.from_mp3(path)

                        final_audio += audio_part
                        final_audio += AudioSegment.silent(
                            duration=120
                        )

                    final_audio = effects.normalize(
                        final_audio,
                        headroom=1.0
                    )

                    output_path = os.path.join(
                        temp_dir,
                        "enhanced_voice.mp3"
                    )

                    final_audio.export(
                        output_path,
                        format="mp3",
                        bitrate="192k"
                    )

                    with open(output_path, "rb") as f:
                        audio_bytes = f.read()

            st.session_state.voice_audio_bytes = audio_bytes

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
            st.code(str(e))


# AUTOMATIC VIDEO EDITOR
st.divider()
st.header("🎬 Automatic Video Editor")

st.write(
    "अपनी Gemini से बनाई हुई Images अपलोड करें। "
    "तैयार Hindi AI Voice अपने-आप वीडियो में जुड़ जाएगी।"
)

uploaded_images = st.file_uploader(
    "📸 अपनी Documentary Images अपलोड करें",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True
)

if uploaded_images:
    st.success(f"आपने {len(uploaded_images)} Images अपलोड की हैं।")

if st.session_state.voice_audio_bytes:
    st.success("Hindi AI Voice तैयार है।")
else:
    st.warning("पहले Hindi AI Voice तैयार करें।")


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
                "आपकी Documentary Video बन रही है..."
            ):

                # IMPORTANT:
                # All temporary files and FFmpeg rendering
                # stay inside this block.

                with tempfile.TemporaryDirectory() as temp_dir:

                    audio_bytes = st.session_state.voice_audio_bytes

                    audio_path = os.path.join(
                        temp_dir,
                        "voice.mp3"
                    )

                    with open(audio_path, "wb") as f:
                        f.write(audio_bytes)

                    audio_duration = AudioSegment.from_file(
                        io.BytesIO(audio_bytes),
                        format="mp3"
                    ).duration_seconds

                    # Sort images by filename
                    sorted_images = sorted(
                        uploaded_images,
                        key=lambda f: [
                            int(x) if x.isdigit() else x.lower()
                            for x in re.split(r'(\d+)', f.name)
                        ]
                    )

                    image_paths = []

                    for i, img in enumerate(sorted_images):

                        ext = os.path.splitext(img.name)[1].lower()

                        if ext not in [
                            ".png", ".jpg", ".jpeg", ".webp"
                        ]:
                            ext = ".png"

                        path = os.path.join(
                            temp_dir,
                            f"scene_{i:04d}{ext}"
                        )

                        with open(path, "wb") as f:
                            f.write(img.getvalue())

                        image_paths.append(path)

                    st.write(
                        f"Saved image files: {len(image_paths)}"
                    )

                    # Video dimensions
                    if quality == "1080p":
                        width, height = 1920, 1080
                    else:
                        width, height = 1280, 720

                    fps = 24
                    transition = 0.5
                    number_of_images = len(image_paths)

                    scene_duration = (
                        audio_duration
                        + (number_of_images - 1) * transition
                    ) / number_of_images

                    if scene_duration <= transition:
                        raise Exception(
                            "Voice बहुत छोटी है। कम Images या लंबी Voice इस्तेमाल करें।"
                        )

                    # FFmpeg inputs
                    command = ["ffmpeg", "-y"]

                    for path in image_paths:
                        command += [
                            "-loop", "1",
                            "-framerate", str(fps),
                            "-t", str(scene_duration),
                            "-i", path
                        ]

                    command += ["-i", audio_path]

                    filters = []

                    # Zoom effect on every image
                    for i in range(number_of_images):

                        filters.append(
                            f"[{i}:v]"
                            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                            f"crop={width}:{height},"
                            f"zoompan=z='min(zoom+0.0005,1.08)':"
                            f"x='iw/2-(iw/zoom/2)':"
                            f"y='ih/2-(ih/zoom/2)':"
                            f"d=1:s={width}x{height}:fps={fps},"
                            f"setsar=1,settb=AVTB,"
                            f"setpts=PTS-STARTPTS,format=yuv420p"
                            f"[v{i}]"
                        )

                    # Fade transitions
                    previous = "[v0]"

                    for i in range(1, number_of_images):

                        output = f"[x{i}]"

                        offset = i * (
                            scene_duration - transition
                        )

                        filters.append(
                            f"{previous}[v{i}]"
                            f"xfade=transition=fade:"
                            f"duration={transition}:"
                            f"offset={offset:.3f}"
                            f"{output}"
                        )

                        previous = output

                    filters.append(
                        f"{previous}format=yuv420p[vout]"
                    )

                    filter_complex = ";".join(filters)

                    output_path = os.path.join(
                        temp_dir,
                        "documentary.mp4"
                    )

                    command += [
                        "-filter_complex",
                        filter_complex,
                        "-map", "[vout]",
                        "-map", f"{number_of_images}:a",
                        "-c:v", "libx264",
                        "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-t", str(audio_duration),
                        "-movflags", "+faststart",
                        output_path
                    ]

                    # Run FFmpeg while images still exist
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=900
                    )

                    if result.returncode != 0:
                        raise Exception(result.stderr[-3000:])

                    if not os.path.exists(output_path):
                        raise Exception("Video file नहीं बनी।")

                    with open(output_path, "rb") as f:
                        video_bytes = f.read()

                # Temporary folder is now safely closed.
                # Video bytes are already in memory.

                st.success("आपकी Documentary Video तैयार है!")
                st.video(video_bytes)

                st.download_button(
                    "📥 Download Documentary MP4",
                    video_bytes,
                    file_name="my_documentary.mp4",
                    mime="video/mp4"
                )

        except Exception as e:

            st.error("वीडियो बनाने में समस्या आई।")
            st.code(str(e))
