
import streamlit as st
import os, re, io, tempfile, asyncio
import numpy as np
import edge_tts
from PIL import Image, ImageDraw, ImageFont
from faster_whisper import WhisperModel
from moviepy import VideoClip, AudioFileClip, concatenate_audioclips

# =========================================================
# AMIR AI DOCUMENTARY STUDIO
# Script analyzer + prompts + Hindi AI voice + uploaded voice
# Left image | Right synchronized subtitles | Audio waveform
# =========================================================

st.set_page_config(
    page_title="AMIR AI DOCUMENTARY STUDIO",
    page_icon="🎬",
    layout="wide"
)

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

MAX_SCENE_WORDS = 30

# -------------------- Helpers --------------------

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

async def make_voice(text, voice, output_path):
    tts = edge_tts.Communicate(text, voice, rate="+0%", volume="+0%")
    await tts.save(output_path)

def get_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
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

def render_frame(t, images, subtitles, samples, duration, width, height, font_size, content_type="Documentary"):
    # Shared subtitle and audio timing for both video modes.
    if content_type == "Book Summary":
        left_w = int(width * 0.43)
        right_w = width - left_w
        pad = int(right_w * 0.075)
        frame = Image.new("RGB", (width, height), (3, 10, 15))
        draw = ImageDraw.Draw(frame)

        # Teal grid on the book side and black panel on the right.
        for x in range(0, left_w, max(35, width // 30)):
            draw.line((x, 0, x, height), fill=(15, 76, 73), width=1)
        for y in range(0, height, max(35, height // 18)):
            draw.line((0, y, left_w, y), fill=(15, 76, 73), width=1)
        draw.rectangle((left_w, 0, width, height), fill=(2, 4, 6))
        for x in range(left_w, width, max(45, width // 22)):
            draw.line((x, 0, x, height), fill=(13, 26, 27), width=1)
        for y in range(0, height, max(45, height // 14)):
            draw.line((left_w, y, width, y), fill=(13, 26, 27), width=1)

        # Yellow display stand under the single uploaded book cover.
        platform_y = int(height * 0.84)
        draw.ellipse((int(left_w*.04), platform_y-18, int(left_w*.96), platform_y+40), fill=(255, 218, 0))
        draw.ellipse((int(left_w*.04), platform_y+12, int(left_w*.96), platform_y+58), fill=(10, 10, 10))

        # One image only: preserve its aspect ratio and keep it static for the whole video.
        book = images[0].copy().convert("RGB")
        book.thumbnail((int(left_w*.78), int(height*.72)), Image.Resampling.LANCZOS)
        bx = (left_w - book.width)//2
        by = max(15, int(height*.07) + (int(height*.70)-book.height)//2)
        shadow = Image.new("RGBA", book.size, (0,0,0,0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((4,4,book.width-1,book.height-1), radius=5, fill=(0,0,0,150))
        frame.paste(shadow, (bx+12,by+12), shadow)
        frame.paste(book, (bx,by))

        title_font = get_font(max(20, int(height*.034)), True)
        sub_font = get_font(font_size if height == 720 else int(font_size*1.35), True)
        small_font = get_font(max(16, int(height*.022)))
        draw.text((left_w+pad, int(height*.07)), "BOOK SUMMARY", font=title_font, fill=(245,245,245))
        active_text = next((item["text"] for item in subtitles if item["start"] <= t < item["end"]), "")
        lines = wrap_lines(draw, active_text, sub_font, right_w-2*pad)
        line_height = int(sub_font.size*1.45)
        total_height = len(lines)*line_height
        top, bottom = int(height*.20), int(height*.61)
        y = top + max(0, (bottom-top-total_height)//2)
        if active_text:
            draw.rounded_rectangle((left_w+pad-12,y-14,width-pad+8,y+total_height+14), radius=12, fill=(10,13,16))
            for line in lines:
                draw.text((left_w+pad,y), line, font=sub_font, fill=(255,255,255), stroke_width=1, stroke_fill=(0,0,0))
                y += line_height

        # White animated waveform under subtitles.
        wave_top, wave_bottom = int(height*.73), int(height*.91)
        center_y = (wave_top+wave_bottom)//2
        count, usable = 54, right_w-2*pad
        gap = max(2, int(usable*.006))
        bar_w = max(2, int((usable-(count-1)*gap)/count))
        sample_rate, window = 8000, int(8000*.035)
        max_amp = (wave_bottom-wave_top)//2
        center_sample = int(t*sample_rate)
        for k in range(count):
            offset = int((k/count-.5)*sample_rate*.4)
            a=max(0,center_sample+offset-window//2); b=min(len(samples),a+window)
            rms=float(np.sqrt(np.mean(samples[a:b]**2))) if b>a else 0.0
            amp=max(3,int(min(1.0,rms*3.8)*max_amp))
            x=left_w+pad+k*(bar_w+gap)
            draw.rounded_rectangle((x,center_y-amp,x+bar_w,center_y+amp), radius=max(1,bar_w//2), fill=(245,245,245))
        draw.text((left_w+pad,int(height*.94)), "AUDIO WAVEFORM", font=small_font, fill=(185,195,195))
        return np.asarray(frame)

    # Original Documentary layout: one uploaded image per scene.
    left_w = int(width * 0.64)
    right_w = width-left_w
    pad = int(right_w*.07)
    scene_index = min(int(t/max(duration,.001)*len(images)), len(images)-1)
    frame = Image.new("RGB", (width,height), (8,13,25))
    frame.paste(images[scene_index], (0,0))
    draw=ImageDraw.Draw(frame)
    draw.rectangle((left_w,0,width,height), fill=(9,14,27))
    draw.rectangle((left_w,0,left_w+5,height), fill=(205,164,91))
    title_font=get_font(max(22,int(height*.035)),True)
    sub_font=get_font(font_size if height==720 else int(font_size*1.35),True)
    small_font=get_font(max(17,int(height*.024)))
    draw.text((left_w+pad,int(height*.055)),"DOCUMENTARY",font=title_font,fill=(225,190,120))
    active_text=next((item["text"] for item in subtitles if item["start"]<=t<item["end"]),"")
    lines=wrap_lines(draw,active_text,sub_font,right_w-2*pad)
    line_height=int(sub_font.size*1.42); total_height=len(lines)*line_height
    y=int(height*.20)+(int(height*.53)-total_height)//2
    if active_text:
        draw.rounded_rectangle((left_w+pad-10,y-12,width-pad+8,y+total_height+12),radius=14,fill=(20,28,44))
        for line in lines:
            draw.text((left_w+pad,y),line,font=sub_font,fill=(255,255,255),stroke_width=1,stroke_fill=(0,0,0)); y+=line_height
    wave_top,wave_bottom=int(height*.79),int(height*.935)
    center_y=(wave_top+wave_bottom)//2
    draw.text((left_w+pad,int(height*.765)),"AUDIO WAVEFORM",font=small_font,fill=(170,183,202))
    count,usable=60,right_w-2*pad; gap=max(2,int(usable*.006)); bar_w=max(2,int((usable-(count-1)*gap)/count))
    sample_rate,window=8000,int(8000*.035); max_amp=(wave_bottom-wave_top)//2; center_sample=int(t*sample_rate)
    for k in range(count):
        offset=int((k/count-.5)*sample_rate*.4); a=max(0,center_sample+offset-window//2); b=min(len(samples),a+window)
        rms=float(np.sqrt(np.mean(samples[a:b]**2))) if b>a else 0.0
        amp=int(min(1.0,rms*3.8)*max_amp); x=left_w+pad+k*(bar_w+gap)
        draw.rounded_rectangle((x,center_y-amp,x+bar_w,center_y+amp),radius=max(1,bar_w//2),fill=(225,177,93))
    draw.text((left_w+pad,int(height*.955)),f"SCENE {scene_index+1:02d}/{len(images):02d} • {int(t//60):02d}:{int(t%60):02d}",font=small_font,fill=(145,158,179))
    return np.asarray(frame)

# -------------------- Sidebar --------------------

st.sidebar.title("VIDEO SETTINGS")

voice_choice = st.sidebar.selectbox(
    "Hindi AI Voice",
    ["Male Voice", "Female Voice"]
)
voice_id = "hi-IN-MadhurNeural" if voice_choice == "Male Voice" else "hi-IN-SwaraNeural"

resolution = st.sidebar.selectbox("Video Resolution", ["720p", "1080p"])
VIDEO_W, VIDEO_H = (1280, 720) if resolution == "720p" else (1920, 1080)

subtitle_size = st.sidebar.slider("Subtitle font size", 24, 48, 34, 2)
subtitle_language = st.sidebar.selectbox(
    "Subtitle language",
    ["Auto Detect", "Hindi", "English"]
)

st.sidebar.caption("No background music. Voice only.")

# -------------------- 1. Script --------------------

st.title("🎬 AMIR AI DOCUMENTARY STUDIO")
st.caption("Script • Scene prompts • Voice • Subtitles • Waveform • MP4")
st.info(
    "Final video mein left side image, right side synchronized subtitles "
    "aur subtitles ke neeche animated sound waveform hogi."
)

content_type = st.radio("Choose Video Type", ["Documentary", "Book Summary"], horizontal=True)
if content_type == "Book Summary":
    st.info("Book Summary: ek book cover image aur apni narration voice upload karein. Wahi image poori video mein rahegi.")
else:
    st.info("Documentary: jitne scenes honge, utni hi images upload karein.")

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
    c4.metric("Estimated Duration", f"{word_count/135:.1f}–{word_count/115:.1f} min")

    with st.expander("View automatically created scenes"):
        for i, scene in enumerate(scenes, 1):
            st.markdown(f"**Scene {i}**")
            st.write(scene)
            st.divider()

# -------------------- 2. Prompts --------------------

st.divider()
st.header("2. Generate Scene-wise Image Prompts")

if st.button("Generate All Image Prompts", disabled=not scenes, use_container_width=True):
    st.session_state["prompts"] = [
        make_prompt(scene, i) for i, scene in enumerate(scenes, 1)
    ]
    st.session_state["prompt_script"] = script

if st.session_state.get("prompt_script") == script and st.session_state.get("prompts"):
    for i, prompt in enumerate(st.session_state["prompts"], 1):
        with st.expander(f"Image Prompt {i}"):
            st.code(prompt, language="text")

# -------------------- 3. Images --------------------

st.divider()
st.header("3. Upload Image")

if content_type == "Documentary":
    st.caption("Images ko scene order mein select karein. Pehli image Scene 1 ke liye hogi.")
    uploaded_images = st.file_uploader(
        "📷 Upload Scene-wise Images", type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True, key="documentary_images"
    ) or []
    images_ready = bool(scenes) and len(uploaded_images) == len(scenes)
    if uploaded_images:
        st.success(f"{len(uploaded_images)} images selected.")
        if len(uploaded_images) != len(scenes):
            st.warning(f"{len(scenes)} scenes hain, lekin {len(uploaded_images)} images select hui hain. Har scene ke liye ek image chahiye.")
else:
    book_image = st.file_uploader(
        "📕 Upload One Book Cover Image", type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=False, key="book_summary_cover"
    )
    uploaded_images = [book_image] if book_image else []
    images_ready = book_image is not None
    if book_image:
        st.success("Book cover image selected.")
        st.image(book_image, caption="Book cover preview", width=240)

# -------------------- 4. Voice --------------------

st.divider()
st.header("4. Add Narration Voice")

audio_mode = st.radio(
    "Choose voice method",
    ["Upload My Voice", "Generate Hindi AI Voice"],
    horizontal=True,
    index=0
)

uploaded_audio = None

if audio_mode == "Upload My Voice":
    st.caption(
        "Neeche button par tap karein. Android file picker khulega. "
        "Wahan Downloads folder kholkar MP3/WAV/M4A select karein."
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
    if st.button("Generate Hindi AI Voice", disabled=not scenes, use_container_width=True):
        status = st.status("Hindi AI voice generate ho rahi hai...")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                voice_data = []
                for i, scene in enumerate(scenes, 1):
                    audio_path = os.path.join(temp_dir, f"voice_{i}.mp3")
                    asyncio.run(make_voice(scene, voice_id, audio_path))
                    with open(audio_path, "rb") as f:
                        voice_data.append(f.read())

            st.session_state["generated_voice"] = voice_data
            st.session_state["generated_voice_script"] = script
            status.update(label="AI voice ready!", state="complete")
        except Exception as error:
                    
            status.update(label="Voice generation failed", state="error")
            st.error(str(error))

    if st.session_state.get("generated_voice_script") == script:
        st.success("AI voice ready.")
        for i, voice_data in enumerate(st.session_state["generated_voice"], 1):
            st.caption(f"Scene {i}")
            st.audio(voice_data, format="audio/mp3")

# -------------------- 5. Render MP4 --------------------

st.divider()
st.header("5. Create Final Documentary MP4")

if audio_mode == "Upload My Voice":
    audio_ready = uploaded_audio is not None
else:
    audio_ready = (
        st.session_state.get("generated_voice_script") == script
        and len(st.session_state.get("generated_voice", [])) == len(scenes)
    )

if not images_ready:
    st.info("Documentary: har scene ke liye ek image; Book Summary: sirf ek book cover image upload karein.")
if not audio_ready:
    st.info("Apni voice upload karein ya AI voice generate karein.")

if st.button(
    "🚀 CREATE FINAL MP4 VIDEO",
    disabled=not (images_ready and audio_ready and (content_type == "Book Summary" or bool(script.strip()))),
    type="primary",
    use_container_width=True
):
    status = st.status("Video ban raha hai...", expanded=True)
    progress = st.progress(0)
    final_video = None
    audio_clip = None

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save images
            image_paths = []
            for i, upload in enumerate(uploaded_images, 1):
                path = os.path.join(temp_dir, f"image_{i}.png")
                Image.open(io.BytesIO(upload.getvalue())).convert("RGB").save(path)
                image_paths.append(path)

            # Prepare audio track
            if audio_mode == "Upload My Voice":
                extension = os.path.splitext(uploaded_audio.name)[1].lower()
                audio_path = os.path.join(temp_dir, "narration" + extension)
                with open(audio_path, "wb") as f:
                    f.write(uploaded_audio.getbuffer())
            else:
                voice_paths = []
                for i, data in enumerate(st.session_state["generated_voice"], 1):
                    path = os.path.join(temp_dir, f"voice_{i}.mp3")
                    with open(path, "wb") as f:
                        f.write(data)
                    voice_paths.append(path)

                voice_clips = [AudioFileClip(path) for path in voice_paths]
                joined_audio = concatenate_audioclips(voice_clips)
                audio_path = os.path.join(temp_dir, "narration.mp3")
                joined_audio.write_audiofile(
                    audio_path,
                    codec="libmp3lame",
                    logger=None
                )
                joined_audio.close()
                for clip in voice_clips:
                    clip.close()

            # Speech recognition
            status.write("Audio se subtitles ban rahe hain...")
            whisper = WhisperModel("tiny", device="cpu", compute_type="int8")
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
                    "Audio se subtitles nahi ban paaye. Saaf audio file try karein."
                )

            status.write(f"{detected.language} subtitles detected. Audio prepare ho raha hai...")

            audio_clip = AudioFileClip(audio_path)
            duration = float(audio_clip.duration)

            samples = audio_clip.to_soundarray(fps=8000)
            if samples.ndim == 2:
                samples = samples.mean(axis=1)
            samples = np.asarray(samples, dtype=np.float32)

            # Prepare images according to selected video type.
            if content_type == "Documentary":
                left_width = int(VIDEO_W * 0.64)
                images = [cover_crop(Image.open(path).convert("RGB"), (left_width, VIDEO_H)) for path in image_paths]
                output_name = "AMIR_AI_DOCUMENTARY.mp4"
            else:
                # A single book cover image stays fixed for the entire video.
                images = [Image.open(image_paths[0]).convert("RGB")]
                output_name = "AMIR_BOOK_SUMMARY.mp4"

            status.write("MP4 render ho raha hai...")
            final_video = VideoClip(
                frame_function=lambda t: render_frame(
                    t, images, subtitles, samples, duration,
                    VIDEO_W, VIDEO_H, subtitle_size, content_type
                ),
                duration=duration
            ).with_audio(audio_clip)

            output_path = os.path.join(temp_dir, output_name)

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
            st.session_state["final_mp4_type"] = content_type
            progress.progress(1.0)
            status.update(label="Documentary video ready!", state="complete", expanded=False)

    except Exception as error:
        status.update(label="Video generation failed", state="error")
        st.error(f"Error: {error}")
        st.warning("Cloud memory error aaye to 720p aur chhoti video try karein.")

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

# -------------------- 6. Download --------------------

if (
    st.session_state.get("final_mp4")
    and st.session_state.get("final_mp4_script") == script
    and st.session_state.get("final_mp4_type", "Documentary") == content_type
):
    st.divider()
    st.header("6. Download Your Video")
    st.success("Your MP4 video is ready!")

    st.download_button(
        "⬇️ DOWNLOAD FINAL DOCUMENTARY MP4",
        data=st.session_state["final_mp4"],
        file_name="AMIR_BOOK_SUMMARY.mp4" if content_type == "Book Summary" else "AMIR_AI_DOCUMENTARY.mp4",
        mime="video/mp4",
        type="primary",
        use_container_width=True
)
