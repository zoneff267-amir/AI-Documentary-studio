
import streamlit as st
import os
import re
import asyncio
import tempfile
import numpy as np
import edge_tts

from PIL import Image
from moviepy import VideoClip, AudioFileClip, concatenate_videoclips


# ================= PAGE CONFIG =================

st.set_page_config(
    page_title="AMIR AI Documentary Studio",
    page_icon="🎬",
    layout="wide"
)


# ================= PROFESSIONAL DESIGN =================

st.markdown("""
<style>
.stApp {
    background-color: #10131b;
}
.main-title {
    color: white;
    font-size: 27px;
    font-weight: 800;
    line-height: 1.2;
}
.sub-title {
    color: #aab4c5;
    font-size: 13px;
    margin-top: 7px;
}
.section-title {
    color: white;
    font-size: 21px;
    font-weight: 700;
    padding-top: 12px;
}
div.stButton > button {
    border-radius: 10px;
    font-weight: 700;
    min-height: 45px;
}
</style>
""", unsafe_allow_html=True)


# ================= LOGO AND TITLE =================

logo_col, title_col = st.columns(
    [1, 3.5],
    vertical_alignment="center"
)

with logo_col:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=125)
    else:
        st.markdown("## 🎬")

with title_col:
    st.markdown(
        '<div class="main-title">AMIR AI DOCUMENTARY STUDIO</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="sub-title">Professional Hindi Documentary Creation</div>',
        unsafe_allow_html=True
    )

st.divider()


# ================= SESSION STATE =================

if "voice_audio" not in st.session_state:
    st.session_state.voice_audio = None

if "prompts" not in st.session_state:
    st.session_state.prompts = []


# ================= SCRIPT =================

st.markdown(
    '<div class="section-title">1. Documentary Script</div>',
    unsafe_allow_html=True
)

script = st.text_area(
    "Paste your Hindi documentary script",
    height=200,
    placeholder="Yahan apni complete Hindi script paste karein..."
)


# ================= PROMPT GENERATOR =================

def split_script(text):
    parts = re.split(r'(?<=[।.!?])\s+', text.strip())
    return [x.strip() for x in parts if x.strip()]


def make_prompts(text, count):

    sentences = split_script(text)

    if not sentences:
        return []

    prompts = []

    for i in range(count):

        index = min(
            int(i * len(sentences) / count),
            len(sentences) - 1
        )

        scene = sentences[index]

        prompt = f"""
Create a cinematic 2D illustrated documentary image.

Scene: {scene}

Visual style:
Professional 2D hand-drawn illustration,
cinematic documentary lighting,
detailed Indian environment,
dramatic storytelling composition.

Main character:
A consistent 30-year-old Indian gentleman,
slightly heavy build,
wearing a sky-blue shirt and black formal pants.

Maintain the same character design in every scene
whenever the character appears.

16:9 widescreen landscape.
No text, no subtitles, no watermark.
No 3D, no anime, no photorealism.
"""
        prompts.append(prompt.strip())

    return prompts


st.markdown(
    '<div class="section-title">2. Image Prompt Generator</div>',
    unsafe_allow_html=True
)

prompt_count = st.selectbox(
    "Number of image prompts",
    [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    index=7
)

if st.button("Generate Image Prompts", use_container_width=True):

    if not script.strip():
        st.error("Please paste your script first.")
    else:
        st.session_state.prompts = make_prompts(
            script,
            prompt_count
        )
        st.success(
            f"{len(st.session_state.prompts)} prompts generated!"
        )


if st.session_state.prompts:
    for i, prompt in enumerate(st.session_state.prompts, 1):
        with st.expander(f"Image Prompt {i}"):
            st.code(prompt, language="text")


# ================= HINDI AI VOICE =================

st.markdown(
    '<div class="section-title">3. Hindi AI Voice Generator</div>',
    unsafe_allow_html=True
)

voice_choice = st.selectbox(
    "Select Hindi Voice",
    ["Male - Madhur", "Female - Swara"]
)

voice_names = {
    "Male - Madhur": "hi-IN-MadhurNeural",
    "Female - Swara": "hi-IN-SwaraNeural"
}


async def generate_voice(text, voice, output_path):

    communicator = edge_tts.Communicate(
        text,
        voice,
        rate="+0%",
        volume="+0%"
    )

    await communicator.save(output_path)


if st.button("Generate Hindi AI Voice", use_container_width=True):

    if not script.strip():
        st.error("Please paste your script first.")

    else:
        try:
            with st.spinner("Generating Hindi AI Voice..."):

                with tempfile.TemporaryDirectory() as folder:

                    audio_path = os.path.join(
                        folder,
                        "voice.mp3"
                    )

                    asyncio.run(
                        generate_voice(
                            script,
                            voice_names[voice_choice],
                            audio_path
                        )
                    )

                    with open(audio_path, "rb") as file:
                        st.session_state.voice_audio = file.read()

            st.success("Hindi AI Voice generated successfully!")

        except Exception as error:
            st.error(f"Voice generation error: {error}")


if st.session_state.voice_audio:

    st.audio(
        st.session_state.voice_audio,
        format="audio/mp3"
    )

    st.download_button(
        "Download Hindi Voice MP3",
        data=st.session_state.voice_audio,
        file_name="Amir_Hindi_Voice.mp3",
        mime="audio/mpeg"
    )


# ================= MULTIPLE IMAGE UPLOAD =================

st.markdown(
    '<div class="section-title">4. Upload All Documentary Images</div>',
    unsafe_allow_html=True
)

st.write(
    "Ek hi baar mein apni saari documentary images select karein."
)

st.info(
    "Phone ke image picker mein pehli image ko long-press karein, "
    "phir baaki images select karke Open dabayein."
)

uploaded_images = st.file_uploader(
    "Select Multiple Images Together",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    key="all_documentary_images"
)


# ================= IMAGE PREVIEW AND NUMBERING =================

if uploaded_images:

    st.success(
        f"Total {len(uploaded_images)} images selected successfully."
    )

    st.subheader("Your Image Sequence")

    for index, image_file in enumerate(uploaded_images, start=1):

        col1, col2 = st.columns([1, 3])

        with col1:
            try:
                preview = Image.open(image_file)
                st.image(
                    preview,
                    use_container_width=True
                )
            except Exception:
                st.warning("Image preview unavailable.")

        with col2:
            st.markdown(f"### Image {index}")
            st.caption(f"Original file: {image_file.name}")
            st.caption(f"Video position: Scene {index}")

        st.divider()

    st.success(
        "All selected images will be used in the same upload order."
    )


# ================= VIDEO SETTINGS =================

st.markdown(
    '<div class="section-title">5. Video Settings</div>',
    unsafe_allow_html=True
)

quality = st.selectbox(
    "Select Video Quality",
    ["720p HD", "1080p Full HD"]
)

if quality == "1080p Full HD":
    resolution = (1920, 1080)
else:
    resolution = (1280, 720)


# ================= CENTER ZOOM EFFECT =================

def create_center_zoom_clip(
    image_path,
    width,
    height,
    duration
):

    image = Image.open(image_path).convert("RGB")

    original_width, original_height = image.size

    scale = max(
        width / original_width,
        height / original_height
    )

    base_width = int(original_width * scale)
    base_height = int(original_height * scale)

    base_image = image.resize(
        (base_width, base_height),
        Image.Resampling.LANCZOS
    )

    def make_frame(t):

        progress = min(
            max(t / max(duration, 0.01), 0),
            1
        )

        # Smooth center Zoom In and Zoom Out
        zoom = 1 + 0.07 * (
            0.5 - 0.5 * np.cos(2 * np.pi * progress)
        )

        new_width = int(base_width * zoom)
        new_height = int(base_height * zoom)

        resized = base_image.resize(
            (new_width, new_height),
            Image.Resampling.LANCZOS
        )

        # Fixed center crop: no side movement
        left = (new_width - width) // 2
        top = (new_height - height) // 2

        frame = resized.crop(
            (
                left,
                top,
                left + width,
                top + height
            )
        )

        return np.asarray(frame)

    return VideoClip(
        frame_function=make_frame,
        duration=duration
    )


# ================= VIDEO CREATION =================

def create_documentary(
    image_paths,
    audio_path,
    output_path,
    resolution
):

    width, height = resolution
    fps = 24

    audio = AudioFileClip(audio_path)

    total_images = len(image_paths)

    if total_images == 0:
        audio.close()
        raise ValueError("No images uploaded.")

    scene_duration = audio.duration / total_images

    clips = []
    final_video = None

    try:

        for image_path in image_paths:

            clip = create_center_zoom_clip(
                image_path,
                width,
                height,
                scene_duration
            )

            clips.append(clip)

        final_video = concatenate_videoclips(
            clips,
            method="compose"
        )

        final_video = final_video.with_audio(audio)

        final_video.write_videofile(
            output_path,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            bitrate="5000k" if width == 1920 else "2500k",
            threads=2,
            logger=None
        )

    finally:

        if final_video is not None:
            final_video.close()

        audio.close()

        for clip in clips:
            clip.close()


# ================= GENERATE DOCUMENTARY =================

st.markdown(
    '<div class="section-title">6. Create Documentary Video</div>',
    unsafe_allow_html=True
)

st.info(
    "Features: All uploaded images, automatic numbering, "
    "Center Zoom In + Zoom Out, Hindi AI Voice and MP4 download. "
    "No side movement and no background music."
)

if st.button(
    "🎬 Create AMIR Documentary Video",
    use_container_width=True
):

    if not uploaded_images:
        st.error("Please upload your images first.")

    elif not st.session_state.voice_audio:
        st.error("Please generate Hindi AI Voice first.")

    else:

        progress = st.progress(0)
        status = st.empty()

        try:

            with tempfile.TemporaryDirectory() as folder:

                status.write("Preparing all numbered images...")

                image_paths = []

                # Upload order is preserved.
                # First upload = Image_1
                # Second upload = Image_2
                # Third upload = Image_3

                for index, uploaded_file in enumerate(
                    uploaded_images,
                    start=1
                ):

                    image_path = os.path.join(
                        folder,
                        f"Image_{index}.jpg"
                    )

                    image = Image.open(
                        uploaded_file
                    ).convert("RGB")

                    image.save(
                        image_path,
                        quality=95
                    )

                    image_paths.append(image_path)

                progress.progress(20)

                audio_path = os.path.join(
                    folder,
                    "Amir_Voice.mp3"
                )

                with open(audio_path, "wb") as file:
                    file.write(st.session_state.voice_audio)

                output_path = os.path.join(
                    folder,
                    "AMIR_Documentary.mp4"
                )

                status.write(
                    f"Creating video with {len(image_paths)} images..."
                )

                create_documentary(
                    image_paths,
                    audio_path,
                    output_path,
                    resolution
                )

                progress.progress(100)

                with open(output_path, "rb") as file:
                    video_bytes = file.read()

                st.success(
                    "Your AMIR Documentary Video is ready!"
                )

                st.video(video_bytes)

                st.download_button(
                    "⬇️ Download AMIR Documentary MP4",
                    data=video_bytes,
                    file_name="AMIR_Documentary.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )

        except Exception as error:
            st.error(f"Video generation error: {error}")

        finally:
            progress.empty()
            status.empty()


# ================= FOOTER =================

st.divider()

st.markdown(
    "<p style='text-align:center;color:#9aa4b2;'>"
    "AMIR AI DOCUMENTARY STUDIO"
    "<br>Professional Documentary Creation"
    "</p>",
    unsafe_allow_html=True
                )
