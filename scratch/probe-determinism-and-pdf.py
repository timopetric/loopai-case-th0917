"""Second pass Q6 (determinism / diff vs pass-1 saved response) and Q7 (PDF text extraction)."""
import sys, json
sys.path.insert(0, "/home/timop/work/loopai/scratch")
from probe_common import call, base_body

SCRATCH = "/home/timop/work/loopai/scratch"


def q6():
    print("### Re-verify determinism today + diff vs pass-1 saved resp-q1-full-14day.json ###")
    old = json.load(open(f"{SCRATCH}/resp-q1-full-14day.json"))
    old_body = old["request_body"]
    old_json = old["response_json"]

    _, r_new = call(old_body, label="re-run identical pass-1 Q1 request", save_to=f"{SCRATCH}/resp-z1-rerun-q1.json")
    new_json = r_new.get("response_json", {})

    print("  identical to pass-1 saved response (full dict equality)?:", new_json == old_json)
    if new_json != old_json:
        for k in set(old_json.keys()) | set(new_json.keys()):
            if old_json.get(k) != new_json.get(k):
                print(f"    differs at key: {k}")
                if k in ("ticks",):
                    print("      old:", old_json.get(k))
                    print("      new:", new_json.get(k))
    else:
        print("  -> fully static: no drift within this session.")


def q7_pdf():
    print("\n### PDF guide fetch + text extraction ###")
    import requests
    url = "https://ai-homework-production-2423.up.railway.app/reporting-api-guide.pdf"
    resp = requests.get(url, timeout=60)
    print(f"  GET {url} -> status={resp.status_code} len={len(resp.content)}")
    pdf_path = f"{SCRATCH}/reporting-api-guide.pdf"
    with open(pdf_path, "wb") as f:
        f.write(resp.content)
    print(f"  saved -> {pdf_path}")

    try:
        from pypdf import PdfReader
    except ImportError:
        print("  pypdf not available in this run")
        return

    reader = PdfReader(pdf_path)
    print(f"  num pages: {len(reader.pages)}")
    full_text = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        full_text.append(text)
    all_text = "\n\n=== PAGE BREAK ===\n\n".join(full_text)
    txt_path = f"{SCRATCH}/reporting-api-guide-pdf-text.txt"
    with open(txt_path, "w") as f:
        f.write(all_text)
    print(f"  extracted text saved -> {txt_path} ({len(all_text)} chars)")


if __name__ == "__main__":
    q6()
    q7_pdf()
