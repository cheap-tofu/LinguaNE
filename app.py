import gradio as gr
from gtts import gTTS
import pandas as pd
from google import genai
from google.genai import types
import json
import pathlib
import subprocess
import time
import os
import re
import concurrent.futures

# 1. CLEAN UP RUNNING SESSIONS
gr.close_all()

# 2. SETUP THE MULTI-KEY POOL
# Add as many keys as you want here. The app will rotate through them automatically.
API_KEYS = [
    "YOUR_API_KEY_HERE"
]
active_key_index = 0

# 3. UNIFIED TRANSLATION ENGINE (Auto-Key Rotation + 503 Fallback)
def unified_translation(direction, target_lang, text_input, audio_path):
    global active_key_index
    print("\n--- [START TRANSLATION REQUEST] ---", flush=True)
    is_english_to_target = direction.startswith("English")

    source_lang = "English" if is_english_to_target else target_lang
    output_lang = target_lang if is_english_to_target else "English"
    safe_text = text_input if text_input else ""

    if not safe_text.strip() and not audio_path:
        print("[DEBUG] No text or audio provided.", flush=True)
        return safe_text, "Please provide text or record audio.", "", None, "", "", "", pd.DataFrame()

    prompt = f"""
    You are a linguistics and cultural expert in the {target_lang} language.
    I am providing an input in {source_lang}. It may be text, or an attached audio file.

    1. If an audio file is attached, transcribe exactly what was spoken in {source_lang}. If it's just text, use the text.
    2. Translate the {source_lang} input into {output_lang}.
    3. Break down the grammar, syntax, and cultural context.

    Input Text (if any): "{safe_text}"

    Respond ONLY with a valid JSON object in the exact following format:
    {{
        "transcription": "The exact text of what was said/inputted in the {source_lang} script",
        "translated_text": "The final translation in the {output_lang} script",
        "translit": "The phonetic pronunciation using English letters",
        "grammar": "A short explanation of the grammar rules applied.",
        "structure": "The sentence pattern (e.g., SOV or SVO)",
        "culture": "A 1-sentence note on how this phrase is used culturally in the region.",
        "breakdown": [["Morpheme 1", "Meaning 1"], ["Morpheme 2", "Meaning 2"]]
    }}
    """

    try:
        contents = [prompt]
        if audio_path and os.path.exists(audio_path):
            print(f"[DEBUG] Reading audio file from: {audio_path}", flush=True)
            audio_bytes = pathlib.Path(audio_path).read_bytes()
            if len(audio_bytes) > 0:
                contents.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"))

        response = None

        # Master Key Rotation Loop
        while active_key_index < len(API_KEYS):
            current_key = API_KEYS[active_key_index]

            # Skip placeholder strings
            if "PASTE_" in current_key:
                active_key_index += 1
                continue

            client = genai.Client(api_key=current_key)
            print(f"[DEBUG] Processing with Key #{active_key_index + 1}...", flush=True)

            try:
                # 503 Overload Retry Loop (Per Key)
                max_retries = 3
                for attempt in range(max_retries):
                    model_to_use = 'gemini-3.6-flash' if attempt < 2 else 'gemini-3.7-flash'
                    print(f"        -> Attempt {attempt + 1}: Using {model_to_use}...", flush=True)

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            client.models.generate_content,
                            model=model_to_use,
                            contents=contents,
                            config=types.GenerateContentConfig(response_mime_type="application/json")
                        )
                        try:
                            response = future.result(timeout=60)
                            break # Success! Break the retry loop.
                        except concurrent.futures.TimeoutError:
                            print(f"[WARN] 60-second timeout reached on {model_to_use}.", flush=True)
                            if attempt == max_retries - 1: raise Exception("Request timed out after 60 seconds.")
                        except Exception as api_err:
                            err_str = str(api_err)
                            if "503" in err_str and attempt < max_retries - 1:
                                print(f"[WARN] Overload error. Retrying...", flush=True)
                                time.sleep(2)
                            else:
                                raise api_err # Escalate to Key Rotation block

                if response:
                    break # Success! Break the Master Key loop.

            except Exception as e:
                err_str = str(e)
                if "429" in err_str:
                    print(f"[WARN] Key #{active_key_index + 1} Quota Exhausted! Swapping to next key...", flush=True)
                    active_key_index += 1
                    if active_key_index >= len(API_KEYS):
                        raise Exception("API Quota Exceeded on ALL provided keys. Please add more fresh keys.")
                elif "404" in err_str:
                     print(f"[WARN] Model deprecated. Passing error...", flush=True)
                     raise e
                else:
                    raise e

        if not response:
            raise Exception("No valid API keys available.")

        print("[DEBUG] Received response from Gemini. Parsing JSON...", flush=True)
        raw_response = response.text.strip()
        data = json.loads(raw_response)

        out_audio = None
        try:
            translit_text = data.get('translit', '').strip()
            if translit_text:
                print("[DEBUG] Generating phonetic TTS...", flush=True)
                tts = gTTS(text=translit_text, lang='hi')
                out_audio = "temp_audio.mp3"
                tts.save(out_audio)
        except Exception as tts_err:
            print(f"[WARN] TTS generation failed: {tts_err}", flush=True)
            out_audio = None

        df_data = data.get('breakdown', [])
        if not df_data: df_data = [["No data", "No data"]]
        df = pd.DataFrame(df_data, columns=["Morpheme", "English Meaning"])

        print("--- [REQUEST COMPLETED SUCCESSFULLY] ---\n", flush=True)
        return (
            data.get('transcription', safe_text),
            data.get('translated_text', ''),
            data.get('translit', ''),
            out_audio,
            data.get('structure', ''),
            data.get('grammar', ''),
            data.get('culture', ''),
            df
        )

    except Exception as e:
        error_msg = f"Translation Error: {str(e)}"
        print(f"[ERROR] {error_msg}", flush=True)
        error_df = pd.DataFrame([["Error", error_msg]], columns=["Morpheme", "English Meaning"])
        return safe_text, error_msg, "Error", None, "Error", "Error", "Error", error_df

def update_direction_choices(lang):
    choices = [f"English to {lang}", f"{lang} to English"]
    return gr.update(choices=choices, value=f"English to {lang}")

# 4. BUILD USER INTERFACE
with gr.Blocks() as demo:
    gr.Markdown("# 🗣️ NE India Multilingual AI Platform")
    gr.Markdown("### Multimodal AI translation and linguistic mapping for under-resourced indigenous languages.")

    with gr.Row():
        target_language = gr.Dropdown(
            choices=["Bodo", "Assamese", "Khasi", "Mizo", "Garo", "Manipuri (Meitei)"],
            value="Bodo", label="🌍 Select Target Language", interactive=True
        )
        direction_dropdown = gr.Dropdown(
            choices=["English to Bodo", "Bodo to English"],
            value="English to Bodo", label="🔄 Select Translation Direction", interactive=True
        )

    with gr.Row():
        audio_in = gr.Audio(sources=["microphone"], type="filepath", label="🎤 Speak your sentence (Multimodal Input)")
        text_in = gr.Textbox(label="✍️ Or type your sentence here", placeholder="Enter text...")

    submit_btn = gr.Button("Translate & Analyze", variant="primary")
    gr.Markdown("---")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 🌐 Translation & Pronunciation")
            translation_out = gr.Textbox(label="Translated Text")
            phonetics_out = gr.Textbox(label="Roman Transliteration (Phonetics)")
            audio_out = gr.Audio(label="Listen to Pronunciation")

        with gr.Column():
            gr.Markdown("### 🧠 Syntax & Culture Analysis")
            struct_out = gr.Textbox(label="Sentence Pattern")
            gram_out = gr.Textbox(label="Grammar Rule")
            cult_out = gr.Textbox(label="Cultural Context 🏛️")

    with gr.Row():
        df_out = gr.Dataframe(headers=["Morpheme", "English Meaning"])

    target_language.change(fn=update_direction_choices, inputs=[target_language], outputs=[direction_dropdown])

    submit_btn.click(
        fn=unified_translation,
        inputs=[direction_dropdown, target_language, text_in, audio_in],
        outputs=[text_in, translation_out, phonetics_out, audio_out, struct_out, gram_out, cult_out, df_out]
    )

# 5. LAUNCH LOCAL GRADIO SERVER
demo.launch(share=False, server_port=7860, prevent_thread_lock=True)

# 6. DOWNLOAD & START CLOUDFLARE TUNNEL
if not os.path.exists("cloudflared"):
    print("Downloading Cloudflare Tunnel binary...", flush=True)
    subprocess.run(["wget", "-q", "-nc", "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", "-O", "cloudflared"])
    subprocess.run(["chmod", "+x", "cloudflared"])

subprocess.run(["pkill", "-f", "cloudflared"])
os.system("./cloudflared tunnel --url http://127.0.0.1:7860 > cloudflare.log 2>&1 &")

print("Generating secure public link...", flush=True)
live_link = None
for _ in range(25):
    time.sleep(1)
    if os.path.exists("cloudflare.log"):
        with open("cloudflare.log", "r") as f:
            log_content = f.read()
        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", log_content)
        if match:
            live_link = match.group(0)
            break

if live_link:
    print("\n" + "="*60, flush=True)
    print(f"🌟 CLICK THIS URL FOR YOUR DEMO:\n{live_link}", flush=True)
    print("="*60 + "\n", flush=True)
else:
    print("\nTunnel setup timed out. Check cloudflare.log for details.", flush=True)
