import streamlit as st
import os
import re
import asyncio
import tempfile
import numpy as np
from PIL import Image
import edge_tts

try:
    from moviepy import VideoClip, AudioFileClip, concatenate_videoclips
except ImportError:
    from moviepy.editor import VideoClip, AudioFileClip, concatenate_videoclips


st.set_page_config(
    page_title="AI Documentary Studio",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 AI Documentary Studio")
st.caption("Hindi AI Voice + Cinematic Documentary Video")


# ---------------- SESSION STATE ----------------

if "voice_audio_bytes" not in st.session_state:
    st.session_state.voice_audio_bytes = None

if "all_prompts" not in st.session_state:
    st.session_state.all_prompts = []


# ---------------- HELPER FUNCTIONS ----------------

def split_script(script):
    sentences = re.split(r'(?<=[।.!?])\s+', script.strip())
    return [s.strip() for s in sentences if s.strip()]


def generate_prompts(script, count):
    sentences = split_script(script)

    if not sentences:
        return []

    prompts = []

    for i in range(count):
        index = min(
            int(i * len(sentences) / count),
            len(sentences) - 1
        )

        scene_text = sentences[index]

        prompt = f"""
Create a cinematic 2D illustrated documentary scene.

Scene idea: {scene_text}

Visual style:
Professional 2D hand-drawn cinematic illustration,
Indian environment, realistic proportions,
dramatic documentary lighting, detailed background,
rich visual storytelling, professional composition.

Main character:
A consistent 30-year-old Indian gentleman,
slightly heavy build, wearing a sky-blue shirt
and black formal pants.

Keep the same character appearance in every scene
whenever the character is visible.

Landscape 16:9 widescreen composition.
No text, no subtitles, no watermark,
no 3D render, no anime.
"""
        prompts.append(prompt.strip())

    return prompts


async def create_voice(text, voice, output_file):
    communicator = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate="+0%",
        volume="+0%"
    )
    await communicator.save(output_file)


def natural_sort_key(name):
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r'(\d+)', name)
    ]


# ---------------- CENTER ZOOM EFFECT ----------------

def create_zoom_frame(image, width, height, duration, fps):

    image = image.convert("RGB")

    img_w, img_h = image.size

    # Image ko screen ke size ke hisaab se fit karein
    cover_scale = max(width / img_w, height / img_h)

    base_w = int(img_w * cover_scale)
    base_h = int(img_h * cover_scale)

    base_image = image.resize(
        (base_w, base_h),
        Image.Resampling.LANCZOS
    )

    def make_frame(t):

        # 0 se 1 tak smooth progress
        progress = min(max(t / max(duration, 0.01), 0), 1)

        # Center Zoom In aur Zoom Out
        # Shuru aur end mein normal size
        # Beech mein maximum zoom
        zoom = 1.0 + 0.07 * (
            0.5 - 0.5 * np.cos(2 * np.pi * progress)
        )

        new_w = int(base_w * zoom)
        new_h = int(base_h * zoom)

        resized = base_image.resize(
            (new_w, new_h),
            Image.Resampling.LANCZOS
        )

        # Hamesha center se crop hoga
        left = (new_w - width) // 2
        top = (new_h - height) // 2

        frame = resized.crop(
            (
                left,
                top,
                left + width,
                top + height
            )
        )

        return np.array(frame)

    return make_frame


# ---------------- VIDEO CREATION ----------------

def build_video(image_files, audio_path, output_path, resolution):

    width, height = resolution
    fps = 24

    audio_clip = AudioFileClip(audio_path)
    audio_duration = audio_clip.duration

    total_images = len(image_files)

    if total_images == 0:
        raise ValueError("Please upload at least one image.")

    scene_duration = audio_duration / total_images

    clips = []

    for image_file in image_files:

        image = Image.open(image_file).convert("RGB")

        make_frame = create_zoom_frame(
            image,
            width,
            height,
            scene_duration,
            fps
        )

        try:
            clip = VideoClip(
                frame_function=make_frame,
                duration=scene_duration
            )
        except TypeError:
            clip = VideoClip(
                make_frame=make_frame,
                duration=scene_duration
            )

        clips.append(clip)

    final_video = concatenate_videoclips(
        clips,
        method="compose"
    )

    try:
        final_video = final_video.with_audio(audio_clip)
    except AttributeError:
        final_video = final_video.set_audio(audio_clip)

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
    audio_clip.close()

    for clip in clips:
        clip.close()


# ---------------- SCRIPT SECTION ----------------

st.header("1. Documentary Script")

script = st.text_area(
    "Paste your Hindi documentary script here",
    height=220,
    placeholder="Yahan apni complete Hindi documentary script paste karein..."
)


# ---------------- PROMPT GENERATOR ----------------

st.header("2. Image Prompt Generator")

image_count = st.selectbox(
    "Kitne image prompts chahiye?",
    [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    index=7
)

if st.button("Generate Image Prompts", use_container_width=True):

    if not script.strip():
        st.error("Please paste your script first.")

    else:
        st.session_state.all_prompts = generate_prompts(
            script,
            image_count
        )

        st.success(
            f"{len(st.session_state.all_prompts)} prompts generated!"
        )


if st.session_state.all_prompts:

    st.subheader("Generated Prompts")

    for i, prompt in enumerate(
        st.session_state.all_prompts,
        start=1
    ):

        with st.expander(f"Image Prompt {i}"):

            st.text_area(
                f"Prompt {i}",
                prompt,
                height=180,
                key=f"prompt_{i}"
            )

            st.button(
                "Copy Prompt",
                key=f"copy_{i}",
                on_click=lambda p=prompt: st.session_state.update(
                    copied_prompt=p
                )
            )

    if "copied_prompt" in st.session_state:
        st.code(st.session_state.copied_prompt)


# ---------------- VOICE SECTION ----------------

st.header("3. Hindi AI Voice Generator")

voice_choice = st.selectbox(
    "Select Hindi Voice",
    [
        "Male Voice - Madhur",
        "Female Voice - Swara"
    ]
)

voice_map = {
    "Male Voice - Madhur": "hi-IN-MadhurNeural",
    "Female Voice - Swara": "hi-IN-SwaraNeural"
}

if st.button("Generate Hindi AI Voice", use_container_width=True):

    if not script.strip():
        st.error("Please enter your script first.")

    else:

        with st.spinner("Generating Hindi AI Voice..."):

            try:

                voice = voice_map[voice_choice]

                with tempfile.TemporaryDirectory() as temp_dir:

                    audio_path = os.path.join(
                        temp_dir,
                        "voice.mp3"
                    )

                    asyncio.run(
                        create_voice(
                            script,
                            voice,
                            audio_path
                        )
                    )

                    with open(audio_path, "rb") as f:
                        st.session_state.voice_audio_bytes = f.read()

                st.success("Hindi AI Voice generated successfully!")

            except Exception as e:
                st.error(f"Voice generation error: {e}")


if st.session_state.voice_audio_bytes:

    st.audio(
        st.session_state.voice_audio_bytes,
        format="audio/mp3"
    )

    st.download_button(
        "Download Hindi Voice MP3",
        data=st.session_state.voice_audio_bytes,
        file_name="hindi_documentary_voice.mp3",
        mime="audio/mpeg"
    )


# ---------------- IMAGE UPLOAD ----------------

st.header("4. Upload Documentary Images")

uploaded_images = st.file_uploader(
    "Upload your Gemini images",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True
)

if uploaded_images:

    st.success(f"{len(uploaded_images)} images uploaded.")

    st.caption(
        "Images ko 01, 02, 03 jaise naam dein, "
        "taaki video mein unka order sahi rahe."
    )

    preview_columns = st.columns(3)

    for i, image_file in enumerate(uploaded_images):

        with preview_columns[i % 3]:

            st.image(
                image_file,
                caption=image_file.name,
                use_container_width=True
            )


# ---------------- VIDEO SETTINGS ----------------

st.header("5. Video Settings")

quality = st.selectbox(
    "Select Video Quality",
    ["720p HD", "1080p Full HD"]
)

if quality == "1080p Full HD":
    resolution = (1920, 1080)
else:
    resolution = (1280, 720)


# ---------------- VIDEO GENERATION ----------------

st.header("6. Create Documentary Video")

st.info(
    "Video mein sabhi uploaded images, "
    "Center Zoom In + Zoom Out Effect "
    "aur Hindi AI Voice use hogi. "
    "Image idhar-udhar move nahi hogi. "
    "Background music nahi hoga."
)

if st.button(
    "🎬 Generate Documentary Video",
    use_container_width=True
):

    if not uploaded_images:

        st.error("Please upload documentary images.")

    elif not st.session_state.voice_audio_bytes:

        st.error("Please generate Hindi AI Voice first.")

    else:

        progress = st.progress(0)
        status = st.empty()

        try:

            with tempfile.TemporaryDirectory() as temp_dir:

                status.write("Preparing images and audio...")

                image_paths = []

                sorted_images = sorted(
                    uploaded_images,
                    key=lambda x: natural_sort_key(x.name)
                )

                for i, uploaded_file in enumerate(sorted_images):

                    image_path = os.path.join(
                        temp_dir,
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

                audio_path = os.path.join(
                    temp_dir,
                    "documentary_voice.mp3"
                )

                with open(audio_path, "wb") as f:
                    f.write(st.session_state.voice_audio_bytes)

                output_path = os.path.join(
                    temp_dir,
                    "AI_Documentary.mp4"
                )

                progress.progress(20)

                status.write(
                    f"Creating video with {len(image_paths)} images..."
                )

                build_video(
                    image_paths,
                    audio_path,
                    output_path,
                    resolution
                )

                progress.progress(100)

                status.write("Video generation completed!")

                with open(output_path, "rb") as f:
                    video_bytes = f.read()

                st.success("Your documentary video is ready!")

                st.video(video_bytes)

                st.download_button(
                    label="⬇️ Download Documentary MP4",
                    data=video_bytes,
                    file_name="AI_Documentary.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )

        except Exception as e:

            st.error(f"Video generation failed: {e}")

        finally:

            progress.empty()
