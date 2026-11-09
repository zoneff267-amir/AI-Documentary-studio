
import streamlit as st
import os, re, io, tempfile, asyncio
import numpy as np
import edge_tts
from PIL import Image, ImageDraw, ImageFont
from faster_whisper import WhisperModel
from moviepy import VideoClip, AudioFileClip, concatenate_audioclips

st.set_page_config(page_title="AMIR AI DOCUMENTARY STUDIO", page_icon="🎬", layout="wide")

MAX_SCENE_WORDS = 30

st.markdown("""
<style>
.stApp {background:#10131b;color:#ffffff}
section[data-testid="stSidebar"] {background:#171c29}
h1,h2,h3 {color:#f5c76b !important}
.stButton button {
    background:#d49b36;color:#111111;font-weight:700;
    border-radius:9px;min-height:44px
}
</style>
""", unsafe_allow_html=True)


# ---------- SCRIPT TO SCENE ----------

def split_long_sentence(sentence, limit):
    words = sentence.split()
    return [
        " ".join(words[i:i + limit])
        for i in range(0, len(words), limit)
        if words[i:i + limit]
    ]


def split_script(text, limit=MAX_SCENE_WORDS):
    if not text or not text.strip():
        return []

    text = re.sub(r"\s+", " ", text.strip())
    sentences = re.split(r"(?<=[।!?])\s+|(?<=[.!?])\s+", text)

    pieces = []

    for sentence in filter(None, (s.strip() for s in sentences)):
        if len(sentence.split()) > limit:
            pieces.extend(split_long_sentence(sentence, limit))
        else:
            pieces.append(sentence)

    scenes, current, count = [], [], 0

    for sentence in pieces:
        n = len(sentence.split())

        if current and count + n > limit:
            scenes.append(" ".join(current))
            current, count = [], 0

        current.append(sentence)
        count += n

    if current:
        scenes.append(" ".join(current))

    return scenes


# ---------- IMAGE PROMPTS ----------

def make_prompt(scene, number):
    return f"""Create a cinematic 2D hand-drawn documentary illustration.

SCENE {number}:
{scene}

STYLE:
Indian environment, cinematic lighting, dramatic storytelling,
professional 2D illustration, detailed composition, 16:9 widescreen.

RECURRING CHARACTER WHEN NEEDED:
30-year-old Indian gentleman, heavier build,
sky-blue shirt and black formal pants.

No text, no watermark, no subtitles, no 3D, no anime."""


# ---------- AI VOICE ----------

async def make_voice(text, voice, output_path):
    tts = edge_tts.Communicate(
        text,
        voice,
        rate="+0%",
        volume="+0%"
    )
    await tts.save(output_path)


# ---------- FONT AND IMAGE HELPERS ----------

def get_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",

        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass

    return ImageFont.load_default()


def cover_crop(image, size):
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


def wrap_lines(draw, text, font, max_width):
    words = text.split()
    lines, line = [], ""

    for word in words:
        candidate = word if not line else line + " " + word

        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word

    if line:
        lines.append(line)

    return lines or [""]


# ---------- VIDEO FRAME DESIGN ----------

def render_frame(t, images, subtitles, samples, duration, width, height, font_size):
    left_w = int(width * 0.64)
    right_w = width - left_w
    pad = int(right_w * 0.07)

    scene_index = min(
        int(t / max(duration, 0.001) * len(images)),
        len(images) - 1
    )

    frame = Image.new("RGB", (width, height), (8, 13, 25))
    frame.paste(images[scene_index], (0, 0))

    draw = ImageDraw.Draw(frame)

    draw.rectangle((left_w, 0, width, height), fill=(9, 14, 27))
    draw.rectangle((left_w, 0, left_w + 5, height), fill=(205, 164, 91))

    title_font = get_font(max(22, int(height * 0.035)), True)

    sub_font = get_font(
        font_size if height == 720 else int(font_size * 1.35),
        True
    )

    small_font = get_font(max(17, int(height * 0.024)))

    draw.text(
        (left_w + pad, int(height * 0.055)),
        "DOCUMENTARY",
        font=title_font,
        fill=(225, 190, 120)
    )

    # Synchronized subtitles
    active_text = ""

    for item in subtitles:
        if item["start"] <= t < item["end"]:
            active_text = item["text"]
            break

    lines = wrap_lines(
        draw,
        active_text,
        sub_font,
        right_w - 2 * pad
    )

    line_height = int(sub_font.size * 1.42)
    total_height = len(lines) * line_height

    y = int(height * 0.20) + (
        int(height * 0.53) - total_height
    ) // 2

    if active_text:
        draw.rounded_rectangle(
            (
                left_w + pad - 10,
                y - 12,
                width - pad + 8,
                y + total_height + 12
            ),
            radius=14,
            fill=(20, 28, 44)
        )

        for line in lines:
            draw.text(
                (left_w + pad, y),
                line,
                font=sub_font,
                fill=(255, 255, 255),
                stroke_width=1,
                stroke_fill=(0, 0, 0)
            )
            y += line_height

    # Animated audio waveform
    wave_top = int(height * 0.79)
    wave_bottom = int(height * 0.935)
    center_y = (wave_top + wave_bottom) // 2

    draw.text(
        (left_w + pad, int(height * 0.765)),
        "AUDIO WAVEFORM",
        font=small_font,
        fill=(170, 183, 202)
    )

    bar_count = 60
    usable_width = right_w - 2 * pad
    gap = max(2, int(usable_width * 0.006))

    bar_width = max(
        2,
        int((usable_width - (bar_count - 1) * gap) / bar_count)
    )

    sample_rate = 8000
    center_sample = int(t * sample_rate)
    window = int(sample_rate * 0.035)
    max_amp = (wave_bottom - wave_top) // 2

    for k in range(bar_count):
        offset = int((k / bar_count - 0.5) * sample_rate * 0.4)

        start = max(
            0,
            center_sample + offset - window // 2
        )

        end = min(len(samples), start + window)

        rms = (
            float(np.sqrt(np.mean(samples[start:end] ** 2)))
            if end > start else 0.0
        )

        amplitude = int(min(1.0, rms * 3.8) * max_amp)
        x = left_w + pad + k * (bar_width + gap)

        draw.rounded_rectangle(
            (
                x,
                center_y - amplitude,
                x + bar_width,
                center_y + amplitude
            ),
            radius=max(1, bar_width // 2),
            fill=(225, 177, 93)
        )

    footer = (
        f"SCENE {scene_index + 1:02d}/{len(images):02d} "
        f" • {int(t // 60):02d}:{int(t % 60):02d}"
    )

    draw.text(
        (left_w + pad, int(height * 0.955)),
        footer,
        font=small_font,
        fill=(145, 158, 179)
    )

    return np.asarray(frame)


# ---------- SIDEBAR SETTINGS ----------

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

VIDEO_W, VIDEO_H = (
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


# ---------- MAIN APP ----------

st.title("🎬 AMIR AI DOCUMENTARY STUDIO")

st.caption(
    "Script • Scene prompts • Voice • Subtitles • Waveform • MP4"
)

st.info(
    "Final video mein left side image, right side synchronized subtitles "
    "aur subtitles ke neeche animated sound waveform hogi."
)


# ---------- 1. SCRIPT ANALYZER ----------

st.header("1. Paste Your Complete Script")

script = st.text_area(
    "Your documentary script",
    height=220,
    placeholder="Yahan apni poori Hindi documentary script paste karein..."
)

scenes = split_script(script)
word_count = len(re.findall(r"\S+", script))

if script.strip():
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Scenes", len(scenes))
    c2.metric("Images Required", len(scenes))
    c3.metric("Total Words", word_count)

    c4.metric(
        "Estimated Duration",
        f"{word_count/135:.1f}–{word_count/115:.1f} min"
    )

    with st.expander("View automatically created scenes"):
        for i, scene in enumerate(scenes, 1):
            st.markdown(f"**Scene {i}**")
            st.write(scene)
            st.divider()


# ---------- 2. IMAGE PROMPTS ----------

st.divider()
st.header("2. Generate Scene-wise Image Prompts")

if st.button(
    "Generate All Image Prompts",
    disabled=not scenes,
    use_container_width=True
):
    st.session_state["prompts"] = [
        make_prompt(scene, i)
        for i, scene in enumerate(scenes, 1)
    ]

    st.session_state["prompt_script"] = script

if (
    st.session_state.get("prompt_script") == script
    and st.session_state.get("prompts")
):
    for i, prompt in enumerate(st.session_state["prompts"], 1):
        with st.expander(f"Image Prompt {i}"):
            st.code(prompt, language="text")


# ---------- 3. UPLOAD IMAGES ----------

st.divider()
st.header("3. Upload Documentary Images")

st.caption(
    "Images ko scene order mein select karein. "
    "Pehli image Scene 1 ke liye hogi."
)

uploaded_images = st.file_uploader(
    "📷 Select Images",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    key="documentary_images"
)

images_ready = (
    bool(scenes)
    and uploaded_images is not None
    and len(uploaded_images) == len(scenes)
)

if uploaded_images:
    st.success(f"{len(uploaded_images)} images selected.")

    if scenes and len(uploaded_images) != len(scenes):
        st.warning(
            f"{len(scenes)} scenes hain, lekin "
            f"{len(uploaded_images)} images select hui hain. "
            "Har scene ke liye ek image chahiye."
        )


# ---------- 4. UPLOAD VOICE ----------

st.divider()
st.header("4. Add Narration Voice")

audio_mode = st.radio(
    "Choose voice method",
    ["Upload My Voice", "Generate Hindi AI Voice"],
    horizontal=True
)

uploaded_audio = None

if audio_mode == "Upload My Voice":

    st.caption(
        "Button par tap karein. Android file picker khulega. "
        "Downloads folder se MP3/WAV/M4A file select karein."
    )

    uploaded_audio = st.file_uploader(
        "📂 UPLOAD VOICE FROM DOWNLOADS",
        type=["mp3", "wav", "m4a"],
        accept_multiple_files=False,
        key="narration_audio"
    )

    if uploaded_audio:
        st.success(f"Audio selected: {uploaded_audio.name}")
        st.audio(uploaded_audio)

else:

    if st.button(
        "Generate Hindi AI Voice",
        disabled=not scenes,
        use_container_width=True
    ):

        status = st.status(
            "Hindi AI voice generate ho rahi hai..."
        )

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                voice_data = []

                for i, scene in enumerate(scenes, 1):
                    audio_path = os.path.join(
                        temp_dir,
                        f"voice_{i}.mp3"
                    )

                    asyncio.run(
                        make_voice(scene, voice_id, audio_path)
                    )

                    with open(audio_path, "rb") as f:
                        voice_data.append(f.read())

            st.session_state["generated_voice"] = voice_data
            st.session_state["generated_voice_script"] = script

            status.update(
                label="AI voice ready!",
                state="complete"
            )

        except Exception as error:
            status.update(
                label="Voice generation failed",
                state="error"
            )
            st.error(str(error))

    if st.session_state.get("generated_voice_script") == script:
        st.success("AI voice ready.")

        for i, voice_data in enumerate(
            st.session_state["generated_voice"], 1
        ):
            st.caption(f"Scene {i}")
            st.audio(voice_data, format="audio/mp3")


# ---------- 5. CREATE VIDEO ----------

st.divider()
st.header("5. Create Final Documentary MP4")

if audio_mode == "Upload My Voice":
    audio_ready = uploaded_audio is not None
else:
    audio_ready = (
        st.session_state.get("generated_voice_script") == script
        and len(
            st.session_state.get("generated_voice", [])
        ) == len(scenes)
    )

if not images_ready:
    st.info("Har scene ke liye ek image select karein.")

if not audio_ready:
    st.info("Apni voice upload karein ya AI voice generate karein.")

if st.button(
    "🚀 CREATE FINAL MP4 VIDEO",
    disabled=not (images_ready and audio_ready),
    type="primary",
    use_container_width=True
):

    status = st.status(
        "Video ban raha hai...",
        expanded=True
    )

    progress = st.progress(0)
    final_video = None
    audio_clip = None

    try:
        with tempfile.TemporaryDirectory() as temp_dir:

            # Save uploaded images
            image_paths = []

            for i, upload in enumerate(uploaded_images, 1):
                path = os.path.join(
                    temp_dir,
                    f"image_{i}.png"
                )

                Image.open(
                    io.BytesIO(upload.getvalue())
                ).convert("RGB").save(path)

                image_paths.append(path)

            # Prepare narration audio
            if audio_mode == "Upload My Voice":

                extension = os.path.splitext(
                    uploaded_audio.name
                )[1].lower()

                audio_path = os.path.join(
                    temp_dir,
                    "narration" + extension
                )

                with open(audio_path, "wb") as f:
                    f.write(uploaded_audio.getbuffer())

            else:
                voice_paths = []

                for i, data in enumerate(
                    st.session_state["generated_voice"], 1
                ):
                    path = os.path.join(
                        temp_dir,
                        f"voice_{i}.mp3"
                    )

                    with open(path, "wb") as f:
                        f.write(data)

                    voice_paths.append(path)

                voice_clips = [
                    AudioFileClip(path)
                    for path in voice_paths
                ]

                joined_audio = concatenate_audioclips(voice_clips)

                audio_path = os.path.join(
                    temp_dir,
                    "narration.mp3"
                )

                joined_audio.write_audiofile(
                    audio_path,
                    codec="libmp3lame",
                    logger=None
                )

                joined_audio.close()

                for clip in voice_clips:
                    clip.close()

            # Automatic subtitles
            status.write("Audio se subtitles ban rahe hain...")

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

            segments, detected = whisper.transcribe(
                audio_path,
                language=lang,
                vad_filter=True,
                beam_size=1
            )

            subtitles = [
                {
                    "start": float(item.start),
                    "end": float(item.end),
                    "text": item.text.strip()
                }
                for item in segments
                if item.text.strip()
            ]

            if not subtitles:
                raise RuntimeError(
                    "Audio se subtitles nahi ban paaye. "
                    "Saaf audio file try karein."
                )

            status.write(
                f"{detected.language} subtitles detected. "
                "Audio prepare ho raha hai..."
            )

            audio_clip = AudioFileClip(audio_path)
            duration = float(audio_clip.duration)

            samples = audio_clip.to_soundarray(fps=8000)

            if samples.ndim == 2:
                samples = samples.mean(axis=1)

            samples = np.asarray(
                samples,
                dtype=np.float32
            )

            # Prepare images in scene order
            left_width = int(VIDEO_W * 0.64)

            images = [
                cover_crop(
                    Image.open(path).convert("RGB"),
                    (left_width, VIDEO_H)
                )
                for path in image_paths
            ]

            # Render MP4
            status.write("MP4 render ho raha hai...")

            final_video = VideoClip(
                frame_function=lambda t: render_frame(
                    t,
                    images,
                    subtitles,
                    samples,
                    duration,
                    VIDEO_W,
                    VIDEO_H,
                    subtitle_size
                ),
                duration=duration
            ).with_audio(audio_clip)

            output_path = os.path.join(
                temp_dir,
                "AMIR_AI_DOCUMENTARY.mp4"
            )

            final_video.write_videofile(
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

            progress.progress(1.0)

            status.update(
                label="Documentary video ready!",
                state="complete",
                expanded=False
            )

    except Exception as error:

        status.update(
            label="Video generation failed",
            state="error"
        )

        st.error(f"Error: {error}")

        st.warning(
            "Cloud memory error aaye to 720p "
            "aur chhoti video try karein."
        )

    finally:

        if final_video is not None:
            try:
                final_video.close()
            except Exception:
                pass

        if audio_clip is not None:
            try:
                audio_clip.close()
            except Exception:
                pass


# ---------- 6. DOWNLOAD MP4 ----------

if (
    st.session_state.get("final_mp4")
    and st.session_state.get("final_mp4_script") == script
):

    st.divider()
    st.header("6. Download Your Documentary")

    st.success("Your MP4 video is ready!")

    st.download_button(
        "⬇️ DOWNLOAD FINAL DOCUMENTARY MP4",
        data=st.session_state["final_mp4"],
        file_name="AMIR_AI_DOCUMENTARY.mp4",
        mime="video/mp4",
        type="primary",
        use_container_width=True
    )
