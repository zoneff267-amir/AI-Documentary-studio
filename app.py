
import streamlit as st
import os
import re
import io
import math
import asyncio
import tempfile
import edge_tts
import numpy as np

from PIL import Image
from moviepy import (
    VideoClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_audioclips
)


# ==========================================
# PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="AMIR AI DOCUMENTARY STUDIO",
    page_icon="🎬",
    layout="wide"
)

# ==========================================
# CUSTOM DESIGN
# ==========================================

st.markdown("""
<style>
.stApp {
    background: #10131b;
    color: #ffffff;
}
section[data-testid="stSidebar"] {
    background: #171c29;
}
h1, h2, h3 {
    color: #f5c76b !important;
}
div[data-testid="stMetric"] {
    background: #1c2433;
    border: 1px solid #394354;
    padding: 15px;
    border-radius: 12px;
}
.stButton button {
    background: #d49b36;
    color: #111111;
    font-weight: bold;
    border-radius: 8px;
    border: none;
    min-height: 45px;
}
.stButton button:hover {
    background: #f0bd58;
    color: #111111;
}
</style>
""", unsafe_allow_html=True)


# ==========================================
# HEADER AND LOGO
# ==========================================

logo_path = "logo.png"

if os.path.exists(logo_path):
    st.image(logo_path, width=260)

st.title("AMIR AI DOCUMENTARY STUDIO")
st.caption("Create cinematic documentary videos with AI Hindi voice")

st.divider()


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def split_scenes(text):
    if not text or not text.strip():
        return []

    scenes = re.split(r"\n\s*\n+", text.strip())

    return [
        scene.strip()
        for scene in scenes
        if scene.strip()
    ]


def count_words(text):
    return len(re.findall(r"\S+", text))


def estimate_duration(words):
    if words <= 0:
        return 0, 0

    # Estimated Hindi narration speed:
    # 115 to 135 words per minute

    minimum = words / 135
    maximum = words / 115

    return minimum, maximum


def create_scene_prompt(scene, number):
    return f"""
Create a cinematic 2D illustrated documentary image.

Scene {number}:
{scene}

Visual style:
Professional finance documentary illustration,
Indian environment,
cinematic lighting,
realistic 2D hand-drawn illustration,
detailed background,
dramatic storytelling composition,
16:9 widescreen aspect ratio.

Recurring main character when relevant:
30-year-old Indian gentleman,
heavier build,
sky-blue shirt,
black formal pants.

No text, no watermark, no subtitles.
Do not use 3D rendering or anime style.
"""


# ==========================================
# VOICE GENERATION
# ==========================================

async def generate_voice(text, voice, output_path):
    communicate = edge_tts.Communicate(
        text,
        voice,
        rate="+0%",
        volume="+0%"
    )

    await communicate.save(output_path)


# ==========================================
# CENTER ZOOM VIDEO FRAME
# ==========================================

def create_zoom_clip(image_path, width, height, duration):

    image = Image.open(image_path).convert("RGB")

    # Resize image to cover the complete video frame
    original_width, original_height = image.size

    scale = max(
        width / original_width,
        height / original_height
    )

    new_width = int(original_width * scale)
    new_height = int(original_height * scale)

    image = image.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS
    )

    # Center crop
    left = (new_width - width) // 2
    top = (new_height - height) // 2

    image = image.crop((
        left,
        top,
        left + width,
        top + height
    ))

    def make_frame(t):

        progress = min(max(t / max(duration, 0.001), 0), 1)

        # Smooth zoom in and zoom out.
        # Fixed center, no camera movement or shaking.

        zoom = 1.0 + 0.055 * (
            0.5 - 0.5 * math.cos(2 * math.pi * progress)
        )

        zoom_width = int(width * zoom)
        zoom_height = int(height * zoom)

        enlarged = image.resize(
            (zoom_width, zoom_height),
            Image.Resampling.LANCZOS
        )

        crop_left = (zoom_width - width) // 2
        crop_top = (zoom_height - height) // 2

        frame = enlarged.crop((
            crop_left,
            crop_top,
            crop_left + width,
            crop_top + height
        ))

        return np.array(frame)

    return VideoClip(
        frame_function=make_frame,
        duration=duration
    )


# ==========================================
# SIDEBAR SETTINGS
# ==========================================

st.sidebar.title("⚙️ Video Settings")

voice_choice = st.sidebar.selectbox(
    "Hindi AI Voice",
    [
        "Male Voice",
        "Female Voice"
    ]
)

if voice_choice == "Male Voice":
    selected_voice = "hi-IN-MadhurNeural"
else:
    selected_voice = "hi-IN-SwaraNeural"


resolution_choice = st.sidebar.selectbox(
    "Video Resolution",
    [
        "720p",
        "1080p"
    ]
)

if resolution_choice == "720p":
    video_width = 1280
    video_height = 720
else:
    video_width = 1920
    video_height = 1080


transition_duration = st.sidebar.slider(
    "Smooth Transition Duration",
    min_value=0.3,
    max_value=1.2,
    value=0.7,
    step=0.1
)

st.sidebar.info(
    "No background music. Only AI voice and images."
)


# ==========================================
# SCRIPT ANALYZER
# ==========================================

st.header("1. Script Analyzer")

script = st.text_area(
    "Paste your complete Hindi documentary script",
    height=250,
    placeholder=(
        "Yahan apni complete script paste karein...\n\n"
        "Har naye scene ke beech ek blank line rakhein."
    ),
    key="main_script"
)

scenes = split_scenes(script)
word_count = count_words(script)

minimum_duration, maximum_duration = estimate_duration(
    word_count
)

if script.strip():

    st.markdown("### 📊 Script Analysis")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Scenes",
        len(scenes)
    )

    col2.metric(
        "Images Required",
        len(scenes)
    )

    col3.metric(
        "Total Words",
        word_count
    )

    col4.metric(
        "Estimated Video",
        f"{minimum_duration:.1f}–{maximum_duration:.1f} min"
    )

    st.success(
        f"आपकी स्क्रिप्ट के लिए {len(scenes)} Images और "
        f"{len(scenes)} Voice Segments की जरूरत होगी।"
    )

    with st.expander("See Scene Breakdown"):

        for i, scene in enumerate(scenes, start=1):

            st.markdown(
                f"**Scene {i} → Image {i}**"
            )

            st.write(scene)

            st.divider()

    st.caption(
        "ध्यान दें: हर दो Scenes के बीच एक खाली लाइन रखें। "
        "वीडियो की वास्तविक अवधि AI Voice की बोलने की गति पर निर्भर करेगी।"
    )

else:

    st.info(
        "अपनी स्क्रिप्ट Paste करें। ऐप अपने-आप Scenes, Images "
        "और अनुमानित वीडियो अवधि बताएगा।"
    )


# ==========================================
# SCENE IMAGE PROMPTS
# ==========================================

st.divider()

st.header("2. Generate Image Prompts")

if st.button(
    "Generate Scene-wise Image Prompts",
    disabled=not scenes,
    use_container_width=True
):

    st.session_state["prompts"] = [
        create_scene_prompt(scene, i)
        for i, scene in enumerate(scenes, start=1)
    ]

    st.session_state["prompt_script"] = script


if (
    "prompts" in st.session_state
    and st.session_state.get("prompt_script") == script
):

    for i, prompt in enumerate(
        st.session_state["prompts"],
        start=1
    ):

        with st.expander(f"Image Prompt {i}"):

            st.code(prompt, language="text")


# ==========================================
# IMAGE UPLOAD
# ==========================================

st.divider()

st.header("3. Upload Documentary Images")

uploaded_images = st.file_uploader(
    "Upload images in scene order",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    key="image_upload"
)

if uploaded_images:

    st.success(
        f"{len(uploaded_images)} images uploaded."
    )

    if scenes and len(uploaded_images) != len(scenes):

        st.warning(
            f"आपकी स्क्रिप्ट में {len(scenes)} Scenes हैं, "
            f"लेकिन आपने {len(uploaded_images)} Images अपलोड की हैं।"
        )

    for i, uploaded in enumerate(uploaded_images, start=1):

        st.write(f"Image {i}: {uploaded.name}")


# ==========================================
# GENERATE AI VOICE
# ==========================================

st.divider()

st.header("4. Generate Hindi AI Voice")

if st.button(
    "Generate Scene-wise AI Voice",
    disabled=not scenes,
    use_container_width=True
):

    voice_segments = []

    progress = st.progress(0)
    status = st.empty()

    try:

        with tempfile.TemporaryDirectory() as temp_dir:

            for i, scene in enumerate(scenes, start=1):

                status.write(
                    f"Generating voice for Scene {i}/{len(scenes)}..."
                )

                output_path = os.path.join(
                    temp_dir,
                    f"voice_{i}.mp3"
                )

                asyncio.run(
                    generate_voice(
                        scene,
                        selected_voice,
                        output_path
                    )
                )

                with open(output_path, "rb") as audio_file:
                    voice_segments.append(audio_file.read())

                progress.progress(
                    i / len(scenes)
                )

        st.session_state["voice_segments"] = voice_segments
        st.session_state["voice_scene_texts"] = list(scenes)
        st.session_state["voice_script"] = script
        st.session_state["voice_type"] = selected_voice

        status.success(
            "All scene voice segments generated successfully!"
        )

    except Exception as error:

        st.error(
            f"Voice generation error: {error}"
        )


if (
    st.session_state.get("voice_script") == script
    and st.session_state.get("voice_type") == selected_voice
    and st.session_state.get("voice_segments")
):

    st.success(
        f"{len(st.session_state['voice_segments'])} voice segments ready."
    )

    for i, audio_data in enumerate(
        st.session_state["voice_segments"],
        start=1
    ):

        st.audio(
            audio_data,
            format="audio/mp3"
        )

        st.caption(f"Scene {i} Voice")


# ==========================================
# VIDEO GENERATION
# ==========================================

st.divider()

st.header("5. Create Final Documentary Video")

voice_ready = (
    st.session_state.get("voice_script") == script
    and st.session_state.get("voice_type") == selected_voice
    and st.session_state.get("voice_scene_texts") == scenes
    and len(st.session_state.get("voice_segments", [])) == len(scenes)
)

images_ready = (
    uploaded_images is not None
    and len(uploaded_images) == len(scenes)
    and len(scenes) > 0
)

if not voice_ready:
    st.info("पहले AI Voice Generate करें।")

if not images_ready:
    st.info("हर Scene के लिए एक Image Upload करें।")


if st.button(
    "🎬 Create Final MP4 Video",
    disabled=not (voice_ready and images_ready),
    use_container_width=True
):

    progress = st.progress(0)
    status = st.empty()

    video_clips = []
    audio_clips = []
    final_video = None
    final_audio = None
    composite = None

    try:

        with tempfile.TemporaryDirectory() as temp_dir:

            image_paths = []
            audio_paths = []

            # Save uploaded images
            for i, uploaded in enumerate(
                uploaded_images,
                start=1
            ):

                image_path = os.path.join(
                    temp_dir,
                    f"image_{i}.png"
                )

                image = Image.open(
                    io.BytesIO(uploaded.getvalue())
                ).convert("RGB")

                image.save(image_path, format="PNG")

                image_paths.append(image_path)

                progress.progress(
                    0.10 * i / len(uploaded_images)
                )

            # Save generated audio
            for i, audio_data in enumerate(
                st.session_state["voice_segments"],
                start=1
            ):

                audio_path = os.path.join(
                    temp_dir,
                    f"voice_{i}.mp3"
                )

                with open(audio_path, "wb") as f:
                    f.write(audio_data)

                audio_paths.append(audio_path)

            # Load audio clips
            status.write("Preparing voice segments...")

            for audio_path in audio_paths:

                audio_clip = AudioFileClip(audio_path)

                audio_clips.append(audio_clip)

            audio_durations = [
                clip.duration
                for clip in audio_clips
            ]

            total_duration = sum(audio_durations)

            if total_duration <= 0:
                raise ValueError("Audio duration is invalid.")

            # Create visual scenes with overlapping crossfades
            status.write(
                "Creating smooth zoom and crossfade transitions..."
            )

            current_start = 0.0

            for i, image_path in enumerate(image_paths):

                audio_duration = audio_durations[i]

                is_last = (i == len(image_paths) - 1)

                # Extend each non-final image into the next scene
                # so the next image can fade in over it.
                extra_duration = (
                    0 if is_last else transition_duration
                )

                visual_duration = (
                    audio_duration + extra_duration
                )

                clip = create_zoom_clip(
                    image_path,
                    video_width,
                    video_height,
                    visual_duration
                )

                # Fixed position, smooth opacity fade.
                if i > 0:

                    fade_length = min(
                        transition_duration,
                        visual_duration
                    )

                    def make_mask_frame(t, fade=fade_length):

                        opacity = min(
                            max(t / max(fade, 0.001), 0.0),
                            1.0
                        )

                        return np.full(
                            (video_height, video_width),
                            opacity,
                            dtype=np.float32
                        )

                    mask_clip = VideoClip(
                        frame_function=make_mask_frame,
                        is_mask=True,
                        duration=visual_duration
                    )

                    clip = clip.with_mask(mask_clip)

                clip = clip.with_start(current_start)

                video_clips.append(clip)

                current_start += audio_duration

                progress.progress(
                    0.10 + 0.50 * (i + 1) / len(image_paths)
                )

            # Combine visual clips
            status.write("Combining documentary scenes...")

            composite = CompositeVideoClip(
                video_clips,
                size=(video_width, video_height)
            ).with_duration(total_duration)

            # Combine voice clips in original order
            final_audio = concatenate_audioclips(
                audio_clips
            )

            final_audio = final_audio.with_duration(
                total_duration
            )

            final_video = composite.with_audio(
                final_audio
            )

            output_path = os.path.join(
                temp_dir,
                "AMIR_AI_DOCUMENTARY.mp4"
            )

            status.write(
                "Rendering final MP4. Please wait..."
            )

            final_video.write_videofile(
                output_path,
                fps=30,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                threads=2,
                logger=None
            )

            with open(output_path, "rb") as video_file:

                st.session_state["final_video"] = (
                    video_file.read()
                )

            progress.progress(1.0)

            status.success(
                "Your documentary video is ready!"
            )

    except Exception as error:

        st.error(
            f"Video generation error: {error}"
        )

    finally:

        if final_video is not None:
            final_video.close()

        if composite is not None:
            composite.close()

        for clip in video_clips:
            try:
                clip.close()
            except Exception:
                pass

        for clip in audio_clips:
            try:
                clip.close()
            except Exception:
                pass


# ==========================================
# FINAL VIDEO DOWNLOAD
# ==========================================

if st.session_state.get("final_video"):

    st.divider()

    st.header("6. Download Your Documentary")

    st.success(
        "Your MP4 documentary is ready to download."
    )

    st.download_button(
        label="⬇️ Download Final Documentary MP4",
        data=st.session_state["final_video"],
        file_name="AMIR_AI_DOCUMENTARY.mp4",
        mime="video/mp4",
        use_container_width=True
    )

    st.caption(
        "Android पर डाउनलोड की गई वीडियो आमतौर पर Downloads folder में मिलेगी। "
        "वहाँ से उसे Gallery में ले जा सकते हैं।"
    )


# ==========================================
# FOOTER
# ==========================================

st.divider()

st.markdown(
    """
    <div style="text-align:center; color:#aab2c0;">
        <h4>AMIR AI DOCUMENTARY STUDIO</h4>
        <p>Made for cinematic storytelling.</p>
    </div>
    """,
    unsafe_allow_html=True
)
