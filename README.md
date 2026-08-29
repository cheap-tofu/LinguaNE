# 🗣️ NE India Multilingual AI Platform

An advanced multimodal AI translation and linguistic mapping platform designed to preserve, translate, and analyze under-resourced indigenous languages of Northeast India.

## 🌟 Key Features
* **Multimodal Input:** Translate typed text or use your microphone for real-time speech-to-text translation.
* **Bilateral Translation:** Seamlessly convert between English and major regional indigenous languages (Bodo, Assamese, Khasi, Mizo, Garo, Manipuri/Meitei).
* **Deep Linguistic Breakdown:** Automatically extracts sentence patterns (SOV/SVO), grammar rules, cultural context notes, and morpheme-by-morpheme lexical meanings.
* **Pronunciation Assistant:** Generates automated phonetic audio pronunciations using text-to-speech technology.
* **Robust Multi-Key Fallback Engine:** Built with a resilient API key rotation and 503-error retry loop to ensure high availability during live demonstrations and hackathons.

## 🛠️ Tech Stack
* **AI Engine:** Google Gemini (`gemini-3.6-flash` and `gemini-3.7-flash`) via the modern `google-genai` SDK.
* **User Interface:** Gradio.
* **Audio Processing:** gTTS (Google Text-to-Speech) & SpeechRecognition.
* **Data Management:** Pandas.

## 🚀 How to Run Locally

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/YOUR_USERNAME/ne-india-multilingual-ai.git](https://github.com/YOUR_USERNAME/ne-india-multilingual-ai.git)
   cd ne-india-multilingual-ai
