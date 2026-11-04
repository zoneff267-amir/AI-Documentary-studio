import streamlit as st
import os
import re
import asyncio
import tempfile
import numpy as np
import edge_tts

from PIL import Image
from moviepy import VideoClip, AudioFileClip, concatenate_videoclips


st.set_page_config(
    page_title="Amir AI Documentary Studio",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 AI Documentary Studio")
st.caption("Hindi AI Voice + Cinematic Documentary Maker")


# ---------------- SESSION STATE ----------------

if "voice_audio" not in st.session_state:
    st.session_state.voice_audio = None

if "prompts" not in st.session_state:
    st.session_state.prompts = []


# ---------------- SCRIPT ----------------

st.header("1. Documentary Script")

script = st.text_area(
    "Apni Hindi documentary script paste karein",
    height=220
)


# ---------------- IMAGE PROMPTS ----------------

def split_script(text):
    parts = re.split(r'(?<=[।.!?])\s+', text.strip())
    return [x.strip() for x in parts if x.strip()]


def make_prompts(text, count):
    sentences = split_script(text)

    if not sentences:
        return []

    result = []

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
Consistent 30-year-old Indian gentleman,
slightly heavy build,
sky-blue shirt and black formal pants.

Maintain the same character design in every scene.

16:9 widescreen landscape.
No text, no subtitles, no watermark.
No 3D, no anime, no photorealism.
"""
        result.append(prompt.strip())

    return result


st.header("2. Image Prompt Generator")

prompt_count = st.selectbox(
    "Number of image prompts",
    [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    index=7
)

if st.button("Generate Image Prompts"):

    if not script.strip():
        st.error("Pehle script paste karein.")

    else:
        st.session_state.prompts = make_prompts(
            script,
            prompt_count
        )

        st.success(
            f"{len(st.session_state.prompts)} prompts ready!"
        )


if st.session_state.prompts:

    for i, prompt in enumerate(st.session_state.prompts, 1):

        with st.expander(f"Image Prompt {i}"):

            st.code(prompt, language="text")


# ---------------- AI VOICE ----------------

st.header("3. Hindi AI Voice Generator")

voice_choice = st.selectbox(
    "Voice select karein",
    [
        "Male - Madhur",
        "Female - Swara"
    ]
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


if st.button("Generate Hindi AI Voice"):

    if not script.strip():

        st.error("Pehle script paste karein.")

    else:

        try:

            with st.spinner("Hindi voice generate ho rahi hai..."):

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

            st.success("Voice successfully generated!")

        except Exception as error:
            st.error(f"Voice error: {error}")


if st.session_state.voice_audio:

    st.audio(
        st.session_state.voice_audio,
        format="audio/mp3"
    )

    st.download_button(
        "Download Voice MP3",
        data=st.session_state.voice_audio,
        file_name="Hindi_Voice.mp3",
        mime="audio/mpeg"
    )


# ---------------- IMAGE UPLOAD ----------------

st.header("4. Upload Documentary Images")

uploaded_images = st.file_uploader(
    "Apni images select karein",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True
)

if uploaded_images:

    st.success(
        f"{len(uploaded_images)} images uploaded."
    )

    st.write("Uploaded image files:")

    for image_file in uploaded_images:
        st.write("•", image_file.name)

    st.caption(
        "Sahi sequence ke liye images ke naam "
        "01, 02, 03 jaise rakhein."
    )


# ---------------- VIDEO QUALITY ----------------

st.header("5. Video Settings")

quality = st.selectbox(
    "Video quality",
    ["720p HD", "1080p Full HD"]
)

if quality == "1080p Full HD":
    resolution = (1920, 1080)
else:
    resolution = (1280, 720)


# ---------------- SORT IMAGES ----------------

def natural_sort_key(filename):

    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", filename)
    ]


# ---------------- CENTER ZOOM ----------------

def create_center_zoom_clip(image_path, width, height, duration):

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

        # Center Zoom In and Zoom Out
        zoom = 1 + 0.07 * (
            0.5 - 0.5 * np.cos(2 * np.pi * progress)
        )

        new_width = int(base_width * zoom)
        new_height = int(base_height * zoom)

        resized = base_image.resize(
            (new_width, new_height),
            Image.Resampling.LANCZOS
        )

        # Crop only from the center.
        # No left, right, up or down movement.
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


# ---------------- BUILD VIDEO ----------------

def create_documentary(image_paths, audio_path, output_path, resolution):

    width, height = resolution
    fps = 24

    audio = AudioFileClip(audio_path)

    total_images = len(image_paths)

    if total_images == 0:
        audio.close()
        raise ValueError("No images uploaded.")

    scene_duration = audio.duration / total_images

    clips = []

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

    final_video.close()
    audio.close()

    for clip in clips:
        clip.close()


# ---------------- GENERATE VIDEO ----------------

st.header("6. Create Documentary Video")

st.info(
    "All uploaded images will be included. "
    "Only center Zoom In and Zoom Out effect will be used. "
    "No side movement, no camera pan and no background music."
)

if st.button(
    "🎬 Generate Documentary Video",
    use_container_width=True
):

    if not uploaded_images:

        st.error("Please upload images.")

    elif not st.session_state.voice_audio:

        st.error("Please generate Hindi voice first.")

    else:

        progress = st.progress(0)
        status = st.empty()

        try:

            with tempfile.TemporaryDirectory() as folder:

                status.write("Preparing images...")

                sorted_images = sorted(
                    uploaded_images,
                    key=lambda x: natural_sort_key(x.name)
                )

                image_paths = []

                for i, uploaded_file in enumerate(sorted_images):

                    image_path = os.path.join(
                        folder,
                        f"image_{i:04d}.jpg"
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
                    "voice.mp3"
                )

                with open(audio_path, "wb") as file:
                    file.write(st.session_state.voice_audio)

                output_path = os.path.join(
                    folder,
                    "documentary.mp4"
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

                st.success("Video successfully created!")

                st.video(video_bytes)

                st.download_button(
                    "⬇️ Download MP4 Video",
                    data=video_bytes,
                    file_name="AI_Documentary.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )

        except Exception as error:

            st.error(f"Video generation error: {error}")

        finally:

            progress.empty()
            status.empty()
