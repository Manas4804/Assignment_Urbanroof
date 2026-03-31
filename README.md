# 🧠 AI-Powered DDR Report Generator

## 📌 Overview

This project is an **Applied AI system** that converts raw inspection and thermal reports into a structured, client-ready **Detailed Diagnostic Report (DDR)**.

The system is designed to go beyond simple text generation by:

* Combining multiple data sources
* Handling incomplete and conflicting data
* Producing a clean, structured, and professional report

---

## 🚀 Features

* 📄 Extracts **text + images** from inspection and thermal PDFs
* 🧹 Removes duplicate thermal images using hashing
* 🤖 Uses AI to **merge, reason, and structure data**
* 🧱 Generates a **strict JSON output** for reliability
* 📑 Converts output into a **clean Markdown DDR report**
* 🖼️ Maps relevant images to corresponding observations

---

## 🏗️ System Architecture

```
Input PDFs
   ↓
Text + Image Extraction (PyMuPDF)
   ↓
Image Deduplication (MD5 Hashing)
   ↓
AI Reasoning Layer (Gemini API)
   ↓
Structured JSON Output
   ↓
Markdown DDR Report Generation
```

---

## ⚙️ Tech Stack

* **Python**
* **PyMuPDF (fitz)** – PDF parsing
* **Gemini API (LLM)** – reasoning + report generation
* **Hashlib (MD5)** – image deduplication
* **Requests** – API calls
* **Markdown** – report output

---

## 📂 Project Structure

```
├── generate_ddr.py        # Main pipeline script
├── output/
│   ├── Main_DDR_Output.md # Final generated report
│   └── images/            # Extracted images
├── Sample Report.pdf
├── Thermal Images.pdf
├── .env                   # API key (not committed)
└── README.md
```

---

## 🔄 How It Works

### 1. Data Extraction

* Extracts text and images from PDFs using PyMuPDF
* Tags images with metadata (page number, source)

### 2. Image Deduplication

* Removes duplicate thermal images using MD5 hashing
* Reduces noise and improves efficiency

### 3. AI Reasoning Layer

* Combines inspection + thermal data
* Avoids duplication
* Handles missing/conflicting information
* Outputs structured JSON

### 4. Report Generation

* Converts JSON into a Markdown DDR
* Places images under relevant sections
* Produces a client-friendly report

---

## ▶️ Setup & Usage

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/ddr-ai-generator.git
cd ddr-ai-generator
```

### 2. Install Dependencies

```bash
pip install pymupdf python-dotenv requests
```

### 3. Add API Key

Create a `.env` file:

```
GEMINI_API_KEY=your_api_key_here
```

### 4. Run the Script

```bash
python generate_ddr.py
```

### 5. Output

* Final report: `output/Main_DDR_Output.md`
* Extracted images: `output/images/`

---

## ⚠️ Limitations

* Relies on LLM reasoning → may struggle with highly ambiguous data
* Image understanding is **context-based**, not full computer vision
* No integration with external validation systems (e.g., building plans)

---

## 🚀 Future Scope

This system can be extended into a **multi-agent AI architecture**:

* 📄 Document Parsing Agent
* 🖼️ Vision Agent (image understanding)
* 🧠 Reasoning Agent (conflict resolution)
* 📑 Report Generation Agent
* ✅ Validation Agent (hallucination detection)

Additional improvements:

* Integration with IoT/building data
* Learning from past reports
* Real-time monitoring and diagnostics

---

## 🎯 Key Highlights

* Focus on **system design**, not just prompting
* Handles **real-world imperfect data**
* Produces **structured, reliable, client-ready output**
* Built for **scalability and generalization**

---

## 📬 Contact

If you have any questions or suggestions, feel free to reach out!

---
