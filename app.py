
import streamlit as st
import os, re, io, tempfile, asyncio
import numpy as np
import edge_tts
from PIL import Image, ImageDraw, ImageFont
from faster_whisper import WhisperModel
from moviepy import VideoClip, AudioFileClip, concatenate_audioclips

st.set_page_config(page_title="AMIR AI DOCUMENTARY STUDIO", page_icon="🎬", layout="wide")
st.markdown("""<style>.stApp{background:#10131b;color:white}section[data-testid="stSidebar"]{background:#171c29}h1,h2,h3{color:#f5c76b!important}.stButton button{background:#d49b36;color:#111;font-weight:700;min-height:44px}</style>""",unsafe_allow_html=True)

def split_script(text, limit=30):
    text=re.sub(r"\s+"," ",(text or "").strip())
    if not text:return []
    sentences=re.split(r"(?<=[।!?])\s+|(?<=[.!?])\s+",text)
    chunks=[]
    for sentence in filter(None,sentences):
        words=sentence.split()
        chunks += [" ".join(words[i:i+limit]) for i in range(0,len(words),limit)]
    scenes=[]; current=[]; count=0
    for chunk in chunks:
        n=len(chunk.split())
        if current and count+n>limit:
            scenes.append(" ".join(current)); current=[]; count=0
        current.append(chunk); count+=n
    if current:scenes.append(" ".join(current))
    return scenes

def make_prompt(scene,n,direction):
    default="""2D hand-drawn Indian documentary illustration, cinematic lighting,
dramatic storytelling, detailed composition, 16:9 widescreen.
Recurring character when needed: 30-year-old Indian gentleman, heavier build,
short neat black hair, sky-blue shirt and black formal pants."""
    return f"""Create a cinematic 2D documentary illustration for Scene {n}.
MASTER CHARACTER / ENVIRONMENT / ART DIRECTION:
{direction.strip() or default}
SCENE NARRATION:
{scene}
CONSISTENCY: Keep the same character face, age, body shape, hairstyle,
clothing, art style, colour palette and visual world across all scenes.
Show a visual matching this narration. 16:9 widescreen.
No text, watermark, subtitles, 3D or anime."""

async def make_voice(text,voice,path):
    await edge_tts.Communicate(text,voice,rate="+0%",volume="+0%").save(path)

def font(size,bold=False):
    paths=[
      "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for p in paths:
        if os.path.exists(p):
            try:return ImageFont.truetype(p,size)
            except:pass
    return ImageFont.load_default()

def crop_fill(im,size):
    w,h=size; scale=max(w/im.width,h/im.height)
    im=im.resize((int(im.width*scale),int(im.height*scale)),Image.Resampling.LANCZOS)
    x=(im.width-w)//2;y=(im.height-h)//2
    return im.crop((x,y,x+w,y+h))

def wrap(draw,text,f,maxw):
    lines=[]; line=""
    for word in text.split():
        test=word if not line else line+" "+word
        if draw.textbbox((0,0),test,font=f)[2]<=maxw:line=test
        else:
            if line:lines.append(line)
            line=word
    if line:lines.append(line)
    return lines or [""]

def waveform(draw,samples,t,x,width,top,bottom,color,bars=54):
    cy=(top+bottom)//2; maxamp=max(3,(bottom-top)//2)
    gap=max(2,int(width*.006)); bw=max(2,int((width-(bars-1)*gap)/bars))
    sr=8000; win=int(sr*.045); center=int(t*sr)
    for k in range(bars):
        off=int((k/max(1,bars-1)-.5)*sr*.35)
        a=max(0,center+off-win//2);b=min(len(samples),a+win)
        rms=float(np.sqrt(np.mean(samples[a:b]**2))) if b>a else 0
        amp=max(3,int(min(1,rms*18)*maxamp))
        xx=x+k*(bw+gap)
        draw.rounded_rectangle((xx,cy-amp,xx+bw,cy+amp),radius=max(1,bw//2),fill=color)
def render(t,images,subs,samples,duration,W,H,fs,mode):
    frame=Image.new("RGB",(W,H),(3,8,13));d=ImageDraw.Draw(frame)
    if mode=="Book Summary":
        left=int(W*.43);pad=int((W-left)*.075)
        for x in range(0,left,max(35,W//30)):d.line((x,0,x,H),fill=(15,65,65))
        for y in range(0,H,max(35,H//18)):d.line((0,y,left,y),fill=(15,65,65))
        d.rectangle((left,0,W,H),fill=(2,5,8))
        book=images[0].copy().convert("RGB");book.thumbnail((int(left*.78),int(H*.70)),Image.Resampling.LANCZOS)
        bx=(left-book.width)//2;by=max(18,(int(H*.72)-book.height)//2+int(H*.04))
        d.ellipse((int(left*.04),int(H*.83),int(left*.96),int(H*.91)),fill=(255,211,0))
        d.ellipse((int(left*.04),int(H*.86),int(left*.96),int(H*.94)),fill=(12,12,12))
        frame.paste(book,(bx,by))
        d.text((left+pad,int(H*.07)),"BOOK SUMMARY",font=font(max(20,int(H*.034)),True),fill="white")
        active=next((s["text"] for s in subs if s["start"]<=t<s["end"]),"")
        f=font(fs if H==720 else int(fs*1.35),True);lines=wrap(d,active,f,W-left-2*pad)
        lh=int(f.size*1.45);total=len(lines)*lh;y=int(H*.20)+max(0,(int(H*.62)-int(H*.20)-total)//2)
        if active:
            d.rounded_rectangle((left+pad-10,y-12,W-pad+8,y+total+12),radius=12,fill=(10,13,16))
            for line in lines:d.text((left+pad,y),line,font=f,fill="white",stroke_width=1,stroke_fill="black");y+=lh
        waveform(d,samples,t,left+pad,W-left-2*pad,int(H*.73),int(H*.91),(245,245,245))
        return np.asarray(frame)
    left=int(W*.64);idx=min(int(t/max(duration,.001)*len(images)),len(images)-1)
    frame.paste(images[idx],(0,0));d=ImageDraw.Draw(frame)
    d.rectangle((left,0,W,H),fill=(9,14,27));d.rectangle((left,0,left+5,H),fill=(205,164,91))
    pad=int((W-left)*.07);d.text((left+pad,int(H*.055)),"DOCUMENTARY",font=font(max(22,int(H*.035)),True),fill=(225,190,120))
    active=next((s["text"] for s in subs if s["start"]<=t<s["end"]),"")
    f=font(fs if H==720 else int(fs*1.35),True);lines=wrap(d,active,f,W-left-2*pad)
    lh=int(f.size*1.42);total=len(lines)*lh;y=int(H*.20)+(int(H*.53)-total)//2
    if active:
        d.rounded_rectangle((left+pad-10,y-12,W-pad+8,y+total+12),radius=14,fill=(20,28,44))
        for line in lines:d.text((left+pad,y),line,font=f,fill="white",stroke_width=1,stroke_fill="black");y+=lh
    waveform(d,samples,t,left+pad,W-left-2*pad,int(H*.80),int(H*.935),(225,177,93),60)
    return np.asarray(frame)

# Settings
st.sidebar.title("VIDEO SETTINGS")
resolution=st.sidebar.selectbox("Resolution",["720p","1080p"])
W,H=(1280,720) if resolution=="720p" else (1920,1080)
fps=st.sidebar.selectbox("FPS",[15,24],index=0)
fs=st.sidebar.slider("Subtitle font size",24,48,34,2)
subtitle_language=st.sidebar.selectbox("Subtitle language",["Auto Detect","Hindi","English"])
voice_choice=st.sidebar.selectbox("Hindi AI voice",["Male Voice","Female Voice"])
voice_id="hi-IN-MadhurNeural" if voice_choice=="Male Voice" else "hi-IN-SwaraNeural"
st.sidebar.caption("Background music OFF — Voice only")

st.title("🎬 AMIR AI DOCUMENTARY STUDIO")
st.caption("Master prompt • Scene prompts • Bulk download • Voice • Subtitles • Waveform • MP4")
mode=st.radio("Choose Video Type",["Documentary","Book Summary"],horizontal=True)
st.info("Book Summary: ek cover image poori video mein rahegi." if mode=="Book Summary" else "Documentary: har scene ke liye ek image upload karein.")

st.header("1. Master Character & Environment Prompt")
direction=st.text_area("Apna master prompt pehle paste karein (optional)",height=160,
 placeholder="Character age, face, hairstyle, kapde, body, art style, environment, lighting, colour palette aur consistency rules...")
st.caption("Yeh master prompt har scene ke image prompt mein automatically add hoga.")

st.header("2. Complete Script")
script=st.text_area("Apni poori Hindi script paste karein",height=220)
scenes=split_script(script);words=len(re.findall(r"\S+",script))
if script.strip():
    a,b,c=st.columns(3);a.metric("Scenes",len(scenes));b.metric("Words",words);c.metric("Images needed",len(scenes) if mode=="Documentary" else 1)
    with st.expander("Scene breakdown"):
        for i,s in enumerate(scenes,1):st.markdown(f"**Scene {i}**");st.write(s)

st.header("3. Generate and Download All Image Prompts")
if st.button("GENERATE ALL IMAGE PROMPTS",disabled=not scenes,use_container_width=True):
    st.session_state["prompts"]=[make_prompt(s,i,direction) for i,s in enumerate(scenes,1)]
    st.session_state["p_script"]=script;st.session_state["p_direction"]=direction
current=(st.session_state.get("p_script")==script and st.session_state.get("p_direction","")==direction and bool(st.session_state.get("prompts")))
if current:
    all_prompts="\n\n".join(f"IMAGE PROMPT {i}\n{'='*48}\n{p}" for i,p in enumerate(st.session_state["prompts"],1))
    st.success(f"{len(st.session_state['prompts'])} prompts ready")
    st.download_button("⬇️ DOWNLOAD ALL IMAGE PROMPTS (.TXT)",all_prompts.encode("utf-8"),"AMIR_ALL_IMAGE_PROMPTS.txt","text/plain",use_container_width=True)
    for i,p in enumerate(st.session_state["prompts"],1):
        with st.expander(f"Image Prompt {i}"):st.code(p)

st.header("4. Upload Images")
if mode=="Documentary":
    uploads=st.file_uploader("Har scene ki image scene order mein upload karein",type=["png","jpg","jpeg","webp"],accept_multiple_files=True) or []
    images_ready=bool(scenes) and len(uploads)==len(scenes)
    if uploads and not images_ready:st.warning(f"{len(scenes)} scenes hain, {len(uploads)} images selected hain.")
else:
    cover=st.file_uploader("One book cover image upload karein",type=["png","jpg","jpeg","webp"])
    uploads=[cover] if cover else [];images_ready=cover is not None
    if cover:st.image(cover,width=220)

st.header("5. Narration Voice")
voice_mode=st.radio("Voice method",["Upload My Voice","Generate Hindi AI Voice"],horizontal=True)
uploaded_audio=None
if voice_mode=="Upload My Voice":
    uploaded_audio=st.file_uploader("Upload MP3 / WAV / M4A voice",type=["mp3","wav","m4a"])
    if uploaded_audio:st.success(f"Selected: {uploaded_audio.name}");st.audio(uploaded_audio)
else:
    if st.button("GENERATE HINDI AI VOICE",disabled=not scenes,use_container_width=True):
        status=st.status("AI voice generating...")
        try:
            with tempfile.TemporaryDirectory() as td:
                data=[]
                for i,s in enumerate(scenes,1):
                    p=os.path.join(td,f"voice_{i}.mp3");asyncio.run(make_voice(s,voice_id,p))
                    with open(p,"rb") as f:data.append(f.read())
            st.session_state["voice_data"]=data;st.session_state["voice_script"]=script
            status.update(label="AI voice ready",state="complete")
        except Exception as e:status.update(label="Voice generation failed",state="error");st.error(str(e))
    if st.session_state.get("voice_script")==script and st.session_state.get("voice_data"):
        for data in st.session_state["voice_data"]:st.audio(data,format="audio/mp3")

st.header("6. Create Final MP4")
if voice_mode=="Upload My Voice":audio_ready=uploaded_audio is not None
else:audio_ready=st.session_state.get("voice_script")==script and len(st.session_state.get("voice_data",[]))==len(scenes)
script_ready=(mode=="Book Summary") or bool(script.strip())
if not images_ready:st.info("Pehle required image(s) upload karein.")
if not audio_ready:st.info("Pehle narration voice upload ya generate karein.")
if st.button("🚀 CREATE FINAL MP4 VIDEO",type="primary",use_container_width=True,disabled=not(images_ready and audio_ready and script_ready)):
    status=st.status("Video processing...",expanded=True);progress=st.progress(0);clip=None;audio=None
    try:
        with tempfile.TemporaryDirectory() as td:
            image_paths=[]
            for i,u in enumerate(uploads,1):
                p=os.path.join(td,f"image_{i}.jpg");im=Image.open(io.BytesIO(u.getvalue())).convert("RGB")
                im.thumbnail((1600,1600),Image.Resampling.LANCZOS);im.save(p,"JPEG",quality=88,optimize=True);image_paths.append(p)
            if voice_mode=="Upload My Voice":
                ext=os.path.splitext(uploaded_audio.name)[1].lower();audio_path=os.path.join(td,"narration"+ext)
                with open(audio_path,"wb") as f:f.write(uploaded_audio.getbuffer())
            else:
                paths=[]
                for i,data in enumerate(st.session_state["voice_data"],1):
                    p=os.path.join(td,f"v{i}.mp3");open(p,"wb").write(data);paths.append(p)
                clips=[AudioFileClip(p) for p in paths];joined=concatenate_audioclips(clips)
                audio_path=os.path.join(td,"narration.mp3");joined.write_audiofile(audio_path,codec="libmp3lame",logger=None)
                joined.close()
                for c in clips:c.close()
            status.write("Voice se subtitles ban rahe hain...")
            model=WhisperModel("tiny",device="cpu",compute_type="int8")
            lang={"Auto Detect":None,"Hindi":"hi","English":"en"}[subtitle_language]
            segments,info=model.transcribe(audio_path,language=lang,vad_filter=True,beam_size=1)
            subs=[{"start":float(s.start),"end":float(s.end),"text":s.text.strip()} for s in segments if s.text.strip()]
            if not subs:raise RuntimeError("Audio se subtitles nahi bane. Clear voice file try karein.")
            audio=AudioFileClip(audio_path);duration=float(audio.duration)
            samples=audio.to_soundarray(fps=8000)
            if samples.ndim==2:samples=samples.mean(axis=1)
            samples=np.asarray(samples,dtype=np.float32)
            if mode=="Documentary":
                left=int(W*.64);images=[crop_fill(Image.open(p).convert("RGB"),(left,H)) for p in image_paths]
                outname="AMIR_AI_DOCUMENTARY.mp4"
            else:images=[Image.open(image_paths[0]).convert("RGB")];outname="AMIR_BOOK_SUMMARY.mp4"
            status.write("MP4 render ho raha hai...")
            clip=VideoClip(frame_function=lambda t:render(t,images,subs,samples,duration,W,H,fs,mode),duration=duration).with_audio(audio)
            outpath=os.path.join(td,outname)
            clip.write_videofile(outpath,fps=fps,codec="libx264",audio_codec="aac",preset="ultrafast",threads=2,logger=None)
            with open(outpath,"rb") as f:st.session_state["mp4"]=f.read()
            st.session_state["mp4_script"]=script;st.session_state["mp4_mode"]=mode
            progress.progress(1.0);status.update(label="Video ready!",state="complete",expanded=False)
    except Exception as e:
        status.update(label="Video generation failed",state="error");st.error(f"Error: {e}")
        st.info("720p aur 15 FPS try karein. Cloud CPU ke hisaab se time lag sakta hai.")
    finally:
        if clip:
            try:clip.close()
            except:pass
        if audio:
            try:audio.close()
            except:pass

if st.session_state.get("mp4") and st.session_state.get("mp4_script")==script and st.session_state.get("mp4_mode")==mode:
    st.header("7. Download Video")
    st.download_button("⬇️ DOWNLOAD FINAL MP4",st.session_state["mp4"],"AMIR_BOOK_SUMMARY.mp4" if mode=="Book Summary" else "AMIR_AI_DOCUMENTARY.mp4","video/mp4",use_container_width=True)
