import io


def make_minimal_pdf_bytes():
    # Minimal PDF header and EOF marker
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


def test_upload_resume_accepts_pdf(client):
    pdf_bytes = make_minimal_pdf_bytes()
    files = {"file": ("resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r = client.post("/upload-resume", files=files)
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["publicUrl"].startswith("/files/")


def test_upload_resume_rejects_invalid_type(client):
    files = {"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
    r = client.post("/upload-resume", files=files)
    assert r.status_code == 400
    assert "Invalid file type" in r.text

