
import streamlit as st
import os
import re
import math
import asyncio
import tempfile
import io
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
# SETTINGS
# ==========================================

st.set_page_config(
    page_title="AMIR AI DOCUMENTARY STUDIO",
    page_icon="🎬",
    layout="wide"
)

MAX_SCENE_WORDS = 30


# ==========================================
# DESIGN
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
# LOGO AND HEADER
# ==========================================

if os.path.exists("logo.png"):
    st.image("logo.png", width=300)

st.title("AMIR AI DOCUMENTARY STUDIO")
st.caption("AI-powered Hindi Documentary Video Creator")
st.divider()


# ==========================================
# AUTOMATIC SCRIPT TO SCENE CONVERTER
# ==========================================

def split_long_sentence(sentence, max_words):
    words = sentence.split()
    chunks = []

    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i + max_words])
        if chunk:
            chunks.append(chunk)

    return chunks


def split_script_into_scenes(text, max_words=MAX_SCENE_WORDS):

    if not text or not text.strip():
        return []

    # Normalize spaces and line breaks.
    text = re.sub(r"\s+", " ", text.strip())

    # Split at sentence endings in Hindi and English.
    sentences = re.split(
        r"(?<=[।!?])\s+|(?<=[.!?])\s+",
        text
    )

    sentences = [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]

    # Break unusually long sentences at word boundaries.
    smaller_sentences = []

    for sentence in sentences:

        words = sentence.split()

        if len(words) > max_words:
            smaller_sentences.extend(
                split_long_sentence(sentence, max_words)
            )
        else:
            smaller_sentences.append(sentence)

    # Combine complete sentences into scenes.
    scenes = []
    current_scene = []
    current_count = 0

    for sentence in smaller_sentences:

        sentence_words = len(sentence.split())

        if (
            current_scene
            and current_count + sentence_words > max_words
        ):
            scenes.append(" ".join(current_scene))
            current_scene = []
            current_count = 0

        current_scene.append(sentence)
        current_count += sentence_words

    if current_scene:
        scenes.append(" ".join(current_scene))

    return scenes


def count_words(text):
    return len(re.findall(r"\S+", text))


def estimate_duration(words):

    if words <= 0:
        return 0, 0

    # Approximate Hindi narration speed.
    return words / 135, words / 115


# ==========================================
# IMAGE PROMPT CREATOR
# ==========================================

def create_scene_prompt(scene, number):

    return f"""
Create a cinematic 2D illustrated documentary image.

SCENE {number}:

{scene}

VISUAL STYLE:
Professional finance documentary illustration.
Indian environment and Indian surroundings.
Cinematic lighting.
Detailed storytelling composition.
Professional 2D hand-drawn illustration.
Dramatic documentary atmosphere.
16:9 widescreen aspect ratio.

RECURRING MAIN CHARACTER WHEN NEEDED:
30-year-old Indian gentleman.
Heavier build.
Sky-blue shirt.
Black formal pants.

IMPORTANT:
No text.
No watermark.
No subtitles.
No 3D rendering.
No anime style.
"""


# ==========================================
# AI VOICE
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
# STABLE CENTER ZOOM
# ==========================================

def create_zoom_clip(image_path, width, height, duration):

    image = Image.open(image_path).convert("RGB")

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

    left = (new_width - width) // 2
    top = (new_height - height) // 2

    image = image.crop((
        left,
        top,
        left + width,
        top + height
    ))

    def make_frame(t):

        progress = min(
            max(t / max(duration, 0.001), 0),
            1
        )

        # Smooth center zoom in and out.
        # No pan, no shake, no random movement.

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

        return np.asarray(frame)

    return VideoClip(
        frame_function=make_frame,
        duration=duration
    )


# ==========================================
# SIDEBAR
# ==========================================

st.sidebar.title("VIDEO SETTINGS")

voice_choice = st.sidebar.selectbox(
    "Hindi AI Voice",
    ["Male Voice", "Female Voice"]
)

if voice_choice == "Male Voice":
    selected_voice = "hi-IN-MadhurNeural"
else:
    selected_voice = "hi-IN-SwaraNeural"


resolution_choice = st.sidebar.selectbox(
    "Video Resolution",
    ["720p", "1080p"]
)

if resolution_choice == "720p":
    video_width = 1280
    video_height = 720
else:
    video_width = 1920
    video_height = 1080


transition_duration = st.sidebar.slider(
    "Smooth Crossfade Duration",
    min_value=0.3,
    max_value=1.2,
    value=0.7,
    step=0.1
)

st.sidebar.info(
    "No background music. Only AI Hindi voice."
)


# ==========================================
# 1. SCRIPT ANALYZER
# ==========================================

st.header("1. Paste Your Complete Script")

st.write(
    "ChatGPT से पूरी स्क्रिप्ट कॉपी करके यहाँ Paste करें। "
    "Scene-wise तोड़ने या Scene Number लिखने की जरूरत नहीं है।"
)

script = st.text_area(
    "Your complete documentary script",
    height=280,
    placeholder="Yahan apni poori Hindi documentary script paste karein...",
    key="main_script"
)

scenes = split_script_into_scenes(script)
word_count = count_words(script)

minimum_duration, maximum_duration = estimate_duration(
    word_count
)

if script.strip():

    st.subheader("AUTOMATIC SCRIPT ANALYSIS")

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
        f"आपकी पूरी स्क्रिप्ट से {len(scenes)} Scenes बनेंगे। "
        f"आपको {len(scenes)} Images की जरूरत होगी।"
    )

    st.caption(
        "Scenes वाक्यों के आधार पर अपने-आप बनाए गए हैं। "
        "लगभग 30 शब्द प्रति Scene का लक्ष्य रखा गया है।"
    )

    with st.expander("View Automatically Created Scenes"):

        for i, scene in enumerate(scenes, start=1):

            st.markdown(f"**Scene {i} — Image {i}**")
            st.write(scene)
            st.divider()

else:

    st.info(
        "पूरी स्क्रिप्ट Paste करते ही Scene, Image और "
        "वीडियो अवधि की गिनती दिखाई देगी।"
    )


# ==========================================
# 2. IMAGE PROMPTS
# ==========================================

st.divider()
st.header("2. Generate Image Prompts")

if st.button(
    "Generate All Scene-wise Image Prompts",
    disabled=not scenes,
    use_container_width=True
):

    st.session_state["prompts"] = [
        create_scene_prompt(scene, i)
        for i, scene in enumerate(scenes, start=1)
    ]

    st.session_state["prompt_script"] = script


if (
    st.session_state.get("prompt_script") == script
    and st.session_state.get("prompts")
):

    for i, prompt in enumerate(
        st.session_state["prompts"],
        start=1
    ):

        with st.expander(f"Image Prompt {i}"):

            st.code(prompt, language="text")


# ==========================================
# 3. UPLOAD IMAGES
# ==========================================

st.divider()
st.header("3. Upload Images")

st.write(
    "Gemini से बनाई गई Images Scene के क्रम में Upload करें। "
    "पहली Image Scene 1 के लिए होगी।"
)

uploaded_images = st.file_uploader(
    "Select all your documentary images",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    key="image_upload"
)

if uploaded_images:

    st.success(
        f"{len(uploaded_images)} Images uploaded."
    )

    if len(uploaded_images) != len(scenes):

        st.warning(
            f"आपकी स्क्रिप्ट में {len(scenes)} Scenes हैं, "
            f"लेकिन आपने {len(uploaded_images)} Images Upload की हैं।"
        )

    for i, uploaded in enumerate(uploaded_images, start=1):
        st.write(f"Image {i}: {uploaded.name}")


# ==========================================
# 4. GENERATE VOICE
# ==========================================

st.divider()
st.header("4. Generate Hindi AI Voice")

if st.button(
    "Generate All Scene-wise Hindi Voice",
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
                    f"Generating voice {i}/{len(scenes)}..."
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

                with open(output_path, "rb") as f:
                    voice_segments.append(f.read())

                progress.progress(
                    i / len(scenes)
                )

        st.session_state["voice_segments"] = voice_segments
        st.session_state["voice_scene_texts"] = list(scenes)
        st.session_state["voice_script"] = script
        st.session_state["voice_type"] = selected_voice

        st.session_state.pop("final_video", None)
        st.session_state.pop("final_video_script", None)

        status.success(
            "All Hindi voice segments are ready!"
        )

    except Exception as error:

        st.error(
            f"Voice generation error: {error}"
        )


voice_ready = (
    st.session_state.get("voice_script") == script
    and st.session_state.get("voice_type") == selected_voice
    and st.session_state.get("voice_scene_texts") == scenes
    and len(st.session_state.get("voice_segments", [])) == len(scenes)
)

if voice_ready:

    st.success(
        f"{len(scenes)} Hindi voice segments are ready."
    )

    for i, audio_data in enumerate(
        st.session_state["voice_segments"],
        start=1
    ):

        st.caption(f"Scene {i} Voice")
        st.audio(audio_data, format="audio/mp3")


# ==========================================
# 5. CREATE VIDEO
# ==========================================

st.divider()
st.header("5. Create Final Documentary")

images_ready = (
    uploaded_images is not None
    and len(uploaded_images) == len(scenes)
    and len(scenes) > 0
)

if not images_ready:
    st.info("हर Scene के लिए एक Image Upload करें।")

if not voice_ready:
    st.info("पहले Hindi AI Voice Generate करें।")


if st.button(
    "CREATE FINAL MP4 VIDEO",
    disabled=not (voice_ready and images_ready),
    use_container_width=True
):

    progress = st.progress(0)
    status = st.empty()

    video_clips = []
    audio_clips = []
    mask_clips = []

    composite = None
    final_video = None
    final_audio = None

    try:

        with tempfile.TemporaryDirectory() as temp_dir:

            image_paths = []
            audio_paths = []

            # Save images
            status.write("Preparing images...")

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

            # Save voice files
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
            status.write("Reading voice durations...")

            for audio_path in audio_paths:

                audio_clip = AudioFileClip(audio_path)
                audio_clips.append(audio_clip)

            audio_durations = [
                clip.duration
                for clip in audio_clips
            ]

            total_duration = sum(audio_durations)

            if total_duration <= 0:
                raise ValueError("Invalid audio duration.")

            # Calculate a safe fade for each scene boundary.
            fade_durations = []

            for i in range(len(audio_durations) - 1):

                safe_fade = min(
                    transition_duration,
                    audio_durations[i] * 0.35,
                    audio_durations[i + 1] * 0.35
                )

                fade_durations.append(
                    max(0.05, safe_fade)
                )

            # Build overlapping visual scenes
            status.write(
                "Creating stable zoom and smooth crossfades..."
            )

            current_start = 0.0

            for i, image_path in enumerate(image_paths):

                audio_duration = audio_durations[i]

                fade_out_overlap = (
                    fade_durations[i]
                    if i < len(fade_durations)
                    else 0.0
                )

                visual_duration = (
                    audio_duration + fade_out_overlap
                )

                clip = create_zoom_clip(
                    image_path,
                    video_width,
                    video_height,
                    visual_duration
                )

                # Fade in every scene except the first.
                if i > 0:

                    fade_in = fade_durations[i - 1]

                    def make_mask_frame(t, fade=fade_in):

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

                    mask_clips.append(mask_clip)
                    clip = clip.with_mask(mask_clip)

                clip = clip.with_start(current_start)

                video_clips.append(clip)

                current_start += audio_duration

                progress.progress(
                    0.10 + 0.45 * (i + 1) / len(image_paths)
                )

            # Composite visual clips
            status.write("Combining all scenes...")

            composite = CompositeVideoClip(
                video_clips,
                size=(video_width, video_height)
            ).with_duration(total_duration)

            # Join all voice segments
            final_audio = concatenate_audioclips(
                audio_clips
            ).with_duration(total_duration)

            final_video = composite.with_audio(
                final_audio
            )

            output_path = os.path.join(
                temp_dir,
                "AMIR_AI_DOCUMENTARY.mp4"
            )

            status.write(
                "Rendering MP4. Please wait..."
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

            with open(output_path, "rb") as f:
                st.session_state["final_video"] = f.read()

            st.session_state["final_video_script"] = script

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
            try:
                final_video.close()
            except Exception:
                pass

        if composite is not None:
            try:
                composite.close()
            except Exception:
                pass

        for clip in video_clips + mask_clips + audio_clips:
            try:
                clip.close()
            except Exception:
                pass


# ==========================================
# 6. DOWNLOAD VIDEO
# ==========================================

if (
    st.session_state.get("final_video")
    and st.session_state.get("final_video_script") == script
):

    st.divider()
    st.header("6. Download Your Documentary")

    st.success("Your final MP4 video is ready!")

    st.download_button(
        label="DOWNLOAD FINAL DOCUMENTARY MP4",
        data=st.session_state["final_video"],
        file_name="AMIR_AI_DOCUMENTARY.mp4",
        mime="video/mp4",
        use_container_width=True
    )

    st.caption(
        "Android में डाउनलोड की गई वीडियो आमतौर पर Downloads folder में मिलेगी। "
        "वहाँ से Gallery में ले जा सकते हैं।"
    )
