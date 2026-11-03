import streamlit as st
import re
import math

st.set_page_config(
    page_title="AI Documentary Studio",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 AI Documentary Studio")
st.subheader("Your Personal AI Video Creator")

st.write("अपनी हिंदी वीडियो स्क्रिप्ट यहाँ डालें")

script = st.text_area(
    "Video Script",
    height=250,
    placeholder="यहाँ अपनी पूरी हिंदी स्क्रिप्ट पेस्ट करें..."
)

images = st.selectbox(
    "कितनी Images चाहिए?",
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

if st.button("Generate Video"):

    if not script.strip():
        st.warning("पहले Script डालें!")

    else:
        sentences = re.split(r'(?<=[।!?])\s+', script.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            st.warning("स्क्रिप्ट में टेक्स्ट नहीं मिला!")

        else:
            total = len(sentences)
            per_scene = math.ceil(total / images)

            all_prompts = []

            st.success("Scene Planning Complete!")

            st.write("Total Images:", images)
            st.write("Voice:", voice)
            st.write("Quality:", quality)

            st.subheader("🎞️ Scene-by-Scene Image Prompts")

            for i in range(images):

                start = i * per_scene
                end = min(start + per_scene, total)

                scene_text = " ".join(sentences[start:end])

                if not scene_text:
                    scene_text = sentences[-1]

                prompt = (
                    "Cinematic 2D illustrated documentary scene, "
                    "Indian setting, realistic lighting, 16:9 widescreen. "
                    "Main character: a 30-year-old Indian man, "
                    "heavier build, wearing a sky-blue shirt "
                    "and black formal pants. "
                    "Keep character design consistent. "
                    "No text, no watermark. Scene: " + scene_text
                )

                all_prompts.append(prompt)

                with st.expander("Scene " + str(i + 1)):
                    st.write("Script:", scene_text)
                    st.code(prompt, language="text")

            st.info(
                "सभी Scene के Image Prompts तैयार हैं। "
                "इन्हें Gemini में इमेज बनाने के लिए इस्तेमाल करें।"
            )

            prompts_text = "\n\n".join(
                f"SCENE {idx + 1}\n{prompt}"
                for idx, prompt in enumerate(all_prompts)
            )

            st.download_button(
                label="📥 Download All Image Prompts",
                data=prompts_text,
                file_name="all_image_prompts.txt",
                mime="text/plain"
            )
