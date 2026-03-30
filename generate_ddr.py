import fitz  # PyMuPDF
import os
import json
import base64
import hashlib
import requests
from dotenv import load_dotenv

load_dotenv()  # Loads .env file — keep that file out of git!

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Set in .env — never hardcode
GEMINI_MODEL   = "gemini-2.5-flash"
GEMINI_URL     = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

if not GEMINI_API_KEY:
    raise EnvironmentError("GEMINI_API_KEY not set. Copy .env.example to .env and add your key.")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Extract text + images from PDFs
# ─────────────────────────────────────────────────────────────────────────────
def extract_pdf_data(pdf_path, output_image_dir, doc_id_prefix):
    os.makedirs(output_image_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    extracted_text = ""
    extracted_images = []

    for page_num, page in enumerate(doc, start=1):
        extracted_text += f"\n--- {doc_id_prefix} | Page {page_num} ---\n"
        extracted_text += page.get_text() + "\n"

        for img_idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            img_bytes = base_image["image"]

            # Skip tiny images (icons, fonts, decorative elements) — under 15 KB
            if len(img_bytes) < 15 * 1024:
                continue

            ext = base_image["ext"]
            img_filename = f"{doc_id_prefix}_p{page_num}_img{img_idx+1}.{ext}"
            img_filepath = os.path.join(output_image_dir, img_filename)

            with open(img_filepath, "wb") as f:
                f.write(img_bytes)

            extracted_images.append({
                "filename": img_filename,
                "filepath": img_filepath,
                "document": doc_id_prefix,
                "page": page_num,
                "bytes": img_bytes,
                "mime": f"image/{ext}"
            })
            extracted_text += f"\n[IMAGE_HERE: {img_filename}]\n"

    return extracted_text, extracted_images


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1b: Deduplicate thermal images by MD5 hash
#   The Thermal PDF repeats the same scans across every page.
#   We keep only one representative per unique image, so we send ~58 real
#   thermal scans to Gemini instead of 5,400 duplicate copies.
# ─────────────────────────────────────────────────────────────────────────────
def deduplicate_images(images):
    """
    Remove exact-duplicate images (same bytes) from a list.
    Keeps the first occurrence (lowest page number).
    Returns (deduplicated_list, total_removed).
    """
    seen_hashes = {}
    unique = []
    removed = 0

    for img in images:
        h = hashlib.md5(img["bytes"]).hexdigest()
        if h not in seen_hashes:
            seen_hashes[h] = img["filename"]
            unique.append(img)
        else:
            removed += 1

    return unique, removed


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Call Gemini — text + thermal images as inline base64 parts
# ─────────────────────────────────────────────────────────────────────────────
def generate_ddr_report(inspection_text, thermal_text, insp_images, thermal_images_unique):
    system_prompt = """You are an expert Applied AI Builder creating a Detailed Diagnostic Report (DDR) from raw inspection data and thermal images.
Merge both an Inspection Report and a Thermal Report into a professional client-ready structured diagnostic report.

You are provided with:
- The full text of both reports
- All inspection image filenames (embedded as [IMAGE_HERE: ...] markers in the text)
- The actual thermal scan images inline (you can see them directly)

Output ONLY a valid JSON object with these exact keys:
1. "Property_Issue_Summary": String.
2. "Area_wise_Observations": Array of objects, each with:
    - "Area": String
    - "Observations": String (combined visual + thermal findings — reference specific thermal temperatures)
    - "Image_References": Array of image filenames relevant to this area. MUST include:
        * Relevant Inspection_* filenames from the [IMAGE_HERE:] markers in the text
        * Relevant Thermal_* filenames from the thermal images you can see
3. "Probable_Root_Cause": String.
4. "Severity_Assessment": Object {"Level": "Low|Medium|High|Critical", "Reasoning": String}
5. "Recommended_Actions": Array of strings.
6. "Additional_Notes": String.
7. "Missing_Unclear_Information": String (use "Not Available" if nothing missing).

STRICT RULES:
- Do NOT invent facts not present in the source documents.
- Use "Not Available" for genuinely missing information.
- If info conflicts between the two reports, explicitly mention the conflict.
- Use plain, client-friendly language.
- Assign Image_References accurately: Inspection images by their [IMAGE_HERE:] page context, thermal images by what they visually show.
- For thermal images you can see: describe the temperature readings and cold/hot spots observed.
"""

    text_content = f"""
{system_prompt}

INSPECTION IMAGE METADATA (extracted from PDF — reference these filenames in Image_References):
{json.dumps([{"filename": i["filename"], "document": i["document"], "page": i["page"]} for i in insp_images], indent=2)}

THERMAL IMAGE METADATA (unique deduplicated scans — you can see these images inline below):
{json.dumps([{"filename": i["filename"], "document": i["document"], "page": i["page"]} for i in thermal_images_unique], indent=2)}

--- INSPECTION REPORT TEXT ---
{inspection_text}

--- THERMAL REPORT TEXT ---
{thermal_text}
"""

    # Build the parts list: start with the text prompt
    parts = [{"text": text_content}]

    # Append each unique thermal image as an inline base64 part
    # Only include JPEG images (real thermal scans, not PNG UI elements)
    thermal_jpegs = [img for img in thermal_images_unique if img["mime"] == "image/jpeg"]
    print(f"  → Sending {len(thermal_jpegs)} unique thermal JPEG scans to Gemini (inline)...")

    for img in thermal_jpegs:
        b64 = base64.b64encode(img["bytes"]).decode("utf-8")
        parts.append({
            "inline_data": {
                "mime_type": img["mime"],
                "data": b64
            }
        })
        # Add a label so Gemini can map what it sees to the filename
        parts.append({"text": f"[Above image is: {img['filename']}]"})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "response_mime_type": "application/json"
        }
    }

    total_img_kb = sum(len(img["bytes"]) for img in thermal_jpegs) // 1024
    print(f"  → Total thermal image payload: ~{total_img_kb} KB")
    print("Calling Gemini 2.5 Flash via REST API...")
    resp = requests.post(GEMINI_URL, json=payload, timeout=300)

    if resp.status_code != 200:
        print(f"❌ API Error {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()

    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    # Strip accidental markdown code fences
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]

    return json.loads(raw.strip())


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Build the final Markdown report
# ─────────────────────────────────────────────────────────────────────────────
def build_markdown_report(ddr, output_file, images_dir):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Detailed Diagnostic Report (DDR)\n\n")

        f.write("## 1. Property Issue Summary\n")
        f.write(ddr.get("Property_Issue_Summary", "Not Available") + "\n\n")

        f.write("## 2. Area-wise Observations\n\n")
        for area in ddr.get("Area_wise_Observations", []):
            f.write(f"### {area.get('Area', 'Unknown Area')}\n")
            f.write(f"{area.get('Observations', 'Not Available')}\n\n")
            refs = area.get("Image_References", [])
            if refs:
                f.write("**Relevant Images:**\n\n")
                for img_name in refs:
                    img_rel_path = os.path.join("images", img_name)
                    f.write(f"![{img_name}]({img_rel_path})\n\n")
            else:
                f.write("*Image Not Available*\n\n")

        f.write("## 3. Probable Root Cause\n")
        f.write(ddr.get("Probable_Root_Cause", "Not Available") + "\n\n")

        sev = ddr.get("Severity_Assessment", {})
        f.write(f"## 4. Severity Assessment: **{sev.get('Level', 'Not Available')}**\n")
        f.write(f"**Reasoning:** {sev.get('Reasoning', 'Not Available')}\n\n")

        f.write("## 5. Recommended Actions\n")
        for action in ddr.get("Recommended_Actions", []):
            f.write(f"- {action}\n")
        f.write("\n")

        f.write("## 6. Additional Notes\n")
        f.write(ddr.get("Additional_Notes", "Not Available") + "\n\n")

        f.write("## 7. Missing or Unclear Information\n")
        f.write(ddr.get("Missing_Unclear_Information", "Not Available") + "\n\n")

    print(f"✅ Report saved → {output_file}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    IMAGES_DIR   = "output/images"
    REPORT_FILE  = "output/Main_DDR_Output.md"

    print("Step 1: Extracting Inspection Report...")
    insp_text, insp_imgs = extract_pdf_data("Sample Report.pdf", IMAGES_DIR, "Inspection")

    print("Step 2: Extracting Thermal Report...")
    therm_text, therm_imgs = extract_pdf_data("Thermal Images.pdf", IMAGES_DIR, "Thermal")

    print(f"  → Extracted {len(insp_imgs)} inspection images, {len(therm_imgs)} thermal images (raw).")

    print("Step 2b: Deduplicating thermal images...")
    therm_imgs_unique, removed = deduplicate_images(therm_imgs)
    print(f"  → {len(therm_imgs_unique)} unique thermal images kept, {removed} duplicates removed.")

    print("Step 3: Calling Gemini AI to generate DDR (with real thermal images)...")
    ddr_json = generate_ddr_report(insp_text, therm_text, insp_imgs, therm_imgs_unique)

    print("Step 4: Building Markdown report...")
    build_markdown_report(ddr_json, REPORT_FILE, IMAGES_DIR)

    print("\n🎉 Done! Open output/Main_DDR_Output.md to see your report.")
