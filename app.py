
import streamlit as st
import os
import re
import asyncio
import tempfile
import io
import numpy as np
import edge_tts

from PIL import Image, ImageDraw, ImageFont
from faster_whisper import WhisperModel
from moviepy import VideoClip, AudioFileClip

st.set_page_config(
    page_title="AMIR AI DOCUMENTARY STUDIO",
    page_icon="🎬",
    layout="wide"
)

MAX_SCENE_WORDS = 30

st.markdown("""
<style>
.stApp {background:#10131b;color:#fff}
section[data-testid="stSidebar"] {background:#171c29}
h1,h2,h3 {color:#f5c76b !important}
.stButton button {
    background:#d49b36;
    color:#111;
    font-weight:bold;
    border-radius:8px;
    min-height:43px
}
</style>
""", unsafe_allow_html=True)

st.title("🎬 AMIR AI DOCUMENTARY STUDIO")
st.caption("AI Documentary Video Creator")
st.info(
    "Video mein left side image, right side subtitles "
    "aur neeche animated audio waveform hogi."
)

# ----------------------------------
# SCRIPT TO SCENE CONVERTER
# ----------------------------------

def split_long_sentence(sentence, max_words):
    words = sentence.split()
    return [
        " ".join(words[i:i + max_words])
        for i in range(0, len(words), max_words)
        if words[i:i + max_words]
    ]


def split_script_into_scenes(text, max_words=MAX_SCENE_WORDS):
    if not text or not text.strip():
        return []

    text = re.sub(r"\s+", " ", text.strip())

    sentences = re.split(
        r"(?<=[।!?])\s+|(?<=[.!?])\s+",
        text
    )

    smaller = []

    for sentence in filter(None, (s.strip() for s in sentences)):
        if len(sentence.split()) > max_words:
            smaller.extend(
                split_long_sentence(sentence, max_words)
            )
        else:
            smaller.append(sentence)

    scenes = []
    current = []
    count = 0

    for sentence in smaller:
        n = len(sentence.split())

        if current and count + n > max_words:
            scenes.append(" ".join(current))
            current = []
            count = 0

        current.append(sentence)
        count += n

    if current:
        scenes.append(" ".join(current))

    return scenes


# ----------------------------------
# IMAGE PROMPT GENERATOR
# ----------------------------------

def create_scene_prompt(scene, number):
    return f"""
Create a cinematic 2D illustrated documentary image.

SCENE {number}:
{scene}

VISUAL STYLE:
Professional 2D hand-drawn documentary illustration.
Indian environment.
Cinematic lighting.
Detailed storytelling composition.
Dramatic documentary atmosphere.
16:9 widescreen.

MAIN CHARACTER WHEN NEEDED:
30-year-old Indian gentleman.
Heavier build.
Sky-blue shirt.
Black formal pants.

IMPORTANT:
No text.
No watermark.
No subtitles.
No 3D rendering.
No anime.
"""


# ----------------------------------
# AI VOICE
# ----------------------------------

async def generate_voice(text, voice, output_path):
    tts = edge_tts.Communicate(
        text,
        voice,
        rate="+0%",
        volume="+0%"
    )
    await tts.save(output_path)


# ----------------------------------
# IMAGE AND FONT HELPERS
# ----------------------------------

def load_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",

        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    for path in paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass

    return ImageFont.load_default()


def cover_image(image, size):
    w, h = size
    iw, ih = image.size

    scale = max(w / iw, h / ih)

    image = image.resize(
        (int(iw * scale), int(ih * scale)),
        Image.Resampling.LANCZOS
    )

    x = (image.width - w) // 2
    y = (image.height - h) // 2

    return image.crop((x, y, x + w, y + h))


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    line = ""

    for word in words:
        trial = word if not line else line + " " + word

        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word

    if line:
        lines.append(line)

    return lines or [""]


# ----------------------------------
# VIDEO FRAME DESIGN
# ----------------------------------

def build_visual_frame(
    t, pics, subtitles, samples,
    duration, W, H, subtitle_size
):
    left = int(W * 0.64)
    right = W - left
    pad = int(right * 0.07)

    scene_idx = min(
        int(t / max(duration, 0.001) * len(pics)),
        len(pics) - 1
    )

    canvas = Image.new("RGB", (W, H), (8, 13, 25))
    canvas.paste(pics[scene_idx], (0, 0))

    draw = ImageDraw.Draw(canvas)

    draw.rectangle(
        (left, 0, W, H),
        fill=(9, 14, 27)
    )

    draw.rectangle(
        (left, 0, left + 5, H),
        fill=(205, 164, 91)
    )

    title_font = load_font(max(22, int(H * 0.035)), True)

    sub_font = load_font(
        subtitle_size if H == 720
        else int(subtitle_size * 1.35),
        True
    )

    small_font = load_font(max(17, int(H * 0.024)))

    draw.text(
        (left + pad, int(H * 0.055)),
        "DOCUMENTARY",
        font=title_font,
        fill=(225, 190, 120)
    )

    # Current subtitle
    caption = ""

    for seg in subtitles:
        if seg["start"] <= t < seg["end"]:
            caption = seg["text"]
            break

    lines = wrap_text(
        draw,
        caption,
        sub_font,
        right - 2 * pad
    )

    line_h = int(sub_font.size * 1.42)
    total = len(lines) * line_h

    y = int(H * 0.20) + (int(H * 0.53) - total) // 2

    if caption:
        draw.rounded_rectangle(
            (left + pad - 10, y - 12, W - pad + 8, y + total + 12),
            radius=14,
            fill=(20, 28, 44)
        )

        for line in lines:
            draw.text(
                (left + pad, y),
                line,
                font=sub_font,
                fill="white",
                stroke_width=1,
                stroke_fill="black"
            )
            y += line_h

    # Animated audio waveform
    wave_top = int(H * 0.79)
    wave_bottom = int(H * 0.935)
    center_y = (wave_top + wave_bottom) // 2

    draw.text(
        (left + pad, int(H * 0.765)),
        "AUDIO WAVEFORM",
        font=small_font,
        fill=(170, 183, 202)
    )

    n = 60
    usable = right - 2 * pad
    gap = max(2, int(usable * 0.006))
    bar_width = max(
        2,
        int((usable - (n - 1) * gap) / n)
    )

    sample_rate = 8000
    center_sample = int(t * sample_rate)
    window = int(sample_rate * 0.035)
    max_amp = (wave_bottom - wave_top) // 2

    for k in range(n):
        offset = int((k / n - 0.5) * sample_rate * 0.4)

        start = max(
            0,
            center_sample + offset - window // 2
        )

        end = min(
            len(samples),
            start + window
        )

        if end > start:
            rms = float(
                np.sqrt(np.mean(samples[start:end] ** 2))
            )
        else:
            rms = 0.0

        amp = int(min(1.0, rms * 3.8) * max_amp)

        x = left + pad + k * (bar_width + gap)

        draw.rounded_rectangle(
            (
                x,
                center_y - amp,
                x + bar_width,
                center_y + amp
            ),
            radius=max(1, bar_width // 2),
            fill=(225, 177, 93)
        )

    footer = (
        f"SCENE {scene_idx + 1:02d}/{len(pics):02d} "
        f" • {int(t // 60):02d}:{int(t % 60):02d}"
    )

    draw.text(
        (left + pad, int(H * 0.955)),
        footer,
        font=small_font,
        fill=(145, 158, 179)
    )

    return np.asarray(canvas)


# ----------------------------------
# SIDEBAR SETTINGS
# ----------------------------------

st.sidebar.title("VIDEO SETTINGS")

voice_choice = st.sidebar.selectbox(
    "Hindi AI Voice",
    ["Male Voice", "Female Voice"]
)

voice_id = (
    "hi-IN-MadhurNeural"
    if voice_choice == "Male Voice"
    else "hi-IN-SwaraNeural"
)

resolution = st.sidebar.selectbox(
    "Video Resolution",
    ["720p", "1080p"]
)

W, H = (
    (1280, 720)
    if resolution == "720p"
    else (1920, 1080)
)

subtitle_size = st.sidebar.slider(
    "Subtitle font size",
    24, 48, 34, 2
)

subtitle_language = st.sidebar.selectbox(
    "Subtitle language",
    ["Auto Detect", "Hindi", "English"]
)

st.sidebar.caption("No background music. Voice only.")


# ----------------------------------
# 1. SCRIPT ANALYZER
# ----------------------------------

st.header("1. Paste Your Complete Script")

script = st.text_area(
    "Your documentary script",
    height=230,
    placeholder="Yahan apni poori Hindi script paste karein..."
)

scenes = split_script_into_scenes(script)

word_count = len(re.findall(r"\S+", script))

if script.strip():
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Scenes", len(scenes))
    c2.metric("Images Required", len(scenes))
    c3.metric("Total Words", word_count)

    c4.metric(
        "Estimated Video",
        f"{word_count / 135:.1f}–{word_count / 115:.1f} min"
    )

    with st.expander("View Automatically Created Scenes"):
        for i, scene in enumerate(scenes, 1):
            st.markdown(f"**Scene {i}**")
            st.write(scene)
            st.divider()


# ----------------------------------
# 2. IMAGE PROMPTS
# ----------------------------------

st.divider()
st.header("2. Scene-wise Image Prompts")

if st.button(
    "Generate All Scene-wise Image Prompts",
    disabled=not scenes,
    use_container_width=True
):
    st.session_state["prompts"] = [
        create_scene_prompt(scene, i)
        for i, scene in enumerate(scenes, 1)
    ]

    st.session_state["prompt_script"] = script

if (
    st.session_state.get("prompt_script") == script
    and st.session_state.get("prompts")
):
    for i, prompt in enumerate(
        st.session_state["prompts"], 1
    ):
        with st.expander(f"Image Prompt {i}"):
            st.code(prompt, language="text")


# ----------------------------------
# 3. UPLOAD IMAGES
# ----------------------------------

st.divider()
st.header("3. Upload Images")

st.write(
    "Images ko scene order mein upload karein. "
    "Pehli image Scene 1 ke liye hogi."
)

uploaded_images = st.file_uploader(
    "Select all documentary images",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True
)

if uploaded_images:
    st.success(f"{len(uploaded_images)} images uploaded.")

    if scenes and len(uploaded_images) != len(scenes):
        st.warning(
            f"{len(scenes)} scenes hain, "
            f"lekin {len(uploaded_images)} images upload hui hain."
        )


# ----------------------------------
# 4. ADD NARRATION AUDIO
# ----------------------------------

st.divider()
st.header("4. Add Narration Audio")

audio_mode = st.radio(
    "Narration kaise add karenge?",
    [
        "Upload my own audio",
        "Generate Hindi AI voice from script"
    ],
    horizontal=True
)

uploaded_audio = None

if audio_mode == "Upload my own audio":

    uploaded_audio = st.file_uploader(
        "Upload complete narration (MP3/WAV/M4A)",
        type=["mp3", "wav", "m4a"]
    )

else:

    if st.button(
        "Generate Hindi AI Voice",
        disabled=not scenes,
        use_container_width=True
    ):

        status = st.status("Hindi AI voice generate ho rahi hai…")

        try:
            with tempfile.TemporaryDirectory() as td:
                voice_bytes = []

                for i, scene in enumerate(scenes, 1):
                    path = os.path.join(td, f"voice_{i}.mp3")

                    asyncio.run(
                        generate_voice(scene, voice_id, path)
                    )

                    with open(path, "rb") as f:
                        voice_bytes.append(f.read())

            st.session_state["generated_voice"] = voice_bytes
            st.session_state["generated_voice_script"] = script

            status.update(
                label="AI voice ready!",
                state="complete"
            )

        except Exception as e:
            status.update(
                label="Voice generation failed",
                state="error"
            )
            st.error(str(e))

    if st.session_state.get("generated_voice_script") == script:
        st.success("AI voice ready.")

        for i, audio in enumerate(
            st.session_state["generated_voice"], 1
        ):
            st.caption(f"Scene {i}")
            st.audio(audio, format="audio/mp3")


# ----------------------------------
# 5. CREATE FINAL VIDEO
# ----------------------------------

st.divider()
st.header("5. Create Documentary MP4")

images_ready = (
    bool(scenes)
    and uploaded_images is not None
    and len(uploaded_images) == len(scenes)
)

audio_ready = (
    uploaded_audio is not None
    if audio_mode == "Upload my own audio"
    else (
        st.session_state.get("generated_voice_script") == script
        and len(st.session_state.get("generated_voice", [])) == len(scenes)
    )
)

if not images_ready:
    st.info("Har scene ke liye ek image upload karein.")

if not audio_ready:
    st.info("Narration audio upload karein ya AI voice generate karein.")


if st.button(
    "🚀 CREATE FINAL MP4 VIDEO",
    disabled=not (images_ready and audio_ready),
    type="primary",
    use_container_width=True
):

    status = st.status("Video ban raha hai…", expanded=True)

    final_clip = None
    audio_clip = None

    try:
        with tempfile.TemporaryDirectory() as td:

            image_paths = []

            for i, uploaded in enumerate(uploaded_images, 1):
                path = os.path.join(td, f"image_{i}.png")

                Image.open(
                    io.BytesIO(uploaded.getvalue())
                ).convert("RGB").save(path)

                image_paths.append(path)

            # Audio file preparation
            if audio_mode == "Upload my own audio":

                audio_path = os.path.join(
                    td,
                    "narration" + os.path.splitext(uploaded_audio.name)[1]
                )

                with open(audio_path, "wb") as f:
                    f.write(uploaded_audio.getbuffer())

            else:
                from moviepy import concatenate_audioclips

                voice_paths = []

                for i, data in enumerate(
                    st.session_state["generated_voice"], 1
                ):
                    path = os.path.join(td, f"voice_{i}.mp3")

                    with open(path, "wb") as f:
                        f.write(data)

                    voice_paths.append(path)

                voice_clips = [
                    AudioFileClip(path)
                    for path in voice_paths
                ]

                joined = concatenate_audioclips(voice_clips)

                audio_path = os.path.join(td, "narration.mp3")

                joined.write_audiofile(
                    audio_path,
                    codec="libmp3lame",
                    logger=None
                )

                joined.close()

                for clip in voice_clips:
                    clip.close()

            # Automatic subtitle generation
            status.write("Audio se subtitles ban rahe hain…")

            whisper = WhisperModel(
                "tiny",
                device="cpu",
                compute_type="int8"
            )

            lang = {
                "Auto Detect": None,
                "Hindi": "hi",
                "English": "en"
            }[subtitle_language]

            iterator, meta = whisper.transcribe(
                audio_path,
                language=lang,
                vad_filter=True,
                beam_size=1
            )

            subtitles = [
                {
                    "start": float(s.start),
                    "end": float(s.end),
                    "text": s.text.strip()
                }
                for s in iterator
                if s.text.strip()
            ]

            if not subtitles:
                raise RuntimeError(
                    "Audio se subtitles nahi ban paaye. "
                    "Clear narration upload karein."
                )

            # Read audio and waveform data
            status.write("Audio waveform prepare ho rahi hai…")

            audio_clip = AudioFileClip(audio_path)
            duration = float(audio_clip.duration)

            samples = audio_clip.to_soundarray(fps=8000)

            if samples.ndim == 2:
                samples = samples.mean(axis=1)

            samples = np.asarray(samples, dtype=np.float32)

            # Prepare images
            pics = [
                cover_image(
                    Image.open(path).convert("RGB"),
                    (int(W * 0.64), H)
                )
                for path in image_paths
            ]

            # Render video
            status.write("MP4 video render ho raha hai…")

            final_clip = VideoClip(
                frame_function=lambda t: build_visual_frame(
                    t,
                    pics,
                    subtitles,
                    samples,
                    duration,
                    W,
                    H,
                    subtitle_size
                ),
                duration=duration
            ).with_audio(audio_clip)

            output_path = os.path.join(
                td,
                "AMIR_AI_DOCUMENTARY.mp4"
            )

            final_clip.write_videofile(
                output_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                threads=2,
                logger=None
            )

            with open(output_path, "rb") as f:
                st.session_state["final_mp4"] = f.read()

            st.session_state["final_mp4_script"] = script

            status.update(
                label="Documentary video ready!",
                state="complete",
                expanded=False
            )

    except Exception as e:

        status.update(
            label="Video generation failed",
            state="error"
        )

        st.error(f"Error: {e}")

        st.warning(
            "Streamlit Cloud par memory error aaye "
            "to 720p aur chhoti duration se try karein."
        )

    finally:

        if final_clip is not None:
            try:
                final_clip.close()
            except Exception:
                pass

        if audio_clip is not None:
            try:
                audio_clip.close()
            except Exception:
                pass


# ----------------------------------
# 6. DOWNLOAD MP4
# ----------------------------------

if (
    st.session_state.get("final_mp4")
    and st.session_state.get("final_mp4_script") == script
):

    st.divider()
    st.header("6. Download Final Documentary")

    st.success("Your MP4 video is ready!")

    st.download_button(
        "⬇️ DOWNLOAD FINAL DOCUMENTARY MP4",
        data=st.session_state["final_mp4"],
        file_name="AMIR_AI_DOCUMENTARY.mp4",
        mime="video/mp4",
        type="primary",
        use_container_width=True
    )
