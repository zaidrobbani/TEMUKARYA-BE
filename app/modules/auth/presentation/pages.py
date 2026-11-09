from fastapi.responses import HTMLResponse

_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "connect-src 'self'; base-uri 'none'; form-action 'none'"
    ),
}

_TEMPLATE = """\
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ - TEMUKARYA</title>
<style>
  body { margin: 0; background: #fff6e5; color: #3f2b22; font-family: Arial, sans-serif; }
  main { max-width: 420px; margin: 0 auto; padding: 48px 16px; }
  label { display: block; margin: 16px 0 6px; font-weight: 600; font-size: 14px; }
  input { width: 100%; box-sizing: border-box; padding: 14px; font-size: 16px;
          border: 1px solid #e5d9c3; border-radius: 12px; }
  button { width: 100%; margin-top: 24px; padding: 14px; font-size: 16px; font-weight: 600;
           color: #fff; background: #6b4a3a; border: 0; border-radius: 12px; }
  button:disabled { opacity: .6; }
  #result { margin-top: 20px; }
  .error { color: #b3261e; }
</style>
</head>
<body>
<main>
  <h1>__TITLE__</h1>
  <p>__INTRO__</p>
  <form id="form">
    __FIELDS__
    <button id="submit" type="submit">__BUTTON__</button>
  </form>
  <p id="result" role="status"></p>
</main>
<script>
  const token = new URLSearchParams(location.search).get("token") || "";
  history.replaceState(null, "", location.pathname);
  const form = document.getElementById("form");
  const button = document.getElementById("submit");
  const result = document.getElementById("result");

  function show(message, isError) {
    result.textContent = message;
    result.className = isError ? "error" : "";
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    button.disabled = true;
    const body = Object.fromEntries(new FormData(form));
    body.token = token;
    try {
      const response = await fetch(location.pathname, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (payload.success) {
        form.hidden = true;
        show(payload.message, false);
        return;
      }
      const detail = (payload.errors || []).map((error) => error.message).join(". ");
      show(detail || payload.message, true);
    } catch (error) {
      show("Tidak dapat terhubung ke server, silakan coba lagi", true);
    }
    button.disabled = false;
  });
</script>
</body>
</html>
"""


def _page(title: str, intro: str, button: str, fields: str = "") -> HTMLResponse:
    html = (
        _TEMPLATE.replace("__TITLE__", title)
        .replace("__INTRO__", intro)
        .replace("__BUTTON__", button)
        .replace("__FIELDS__", fields)
    )
    return HTMLResponse(html, headers=_HEADERS)


def verify_email_page() -> HTMLResponse:
    return _page(
        "Verifikasi email",
        "Tekan tombol di bawah untuk menyelesaikan verifikasi email akun kamu.",
        "Verifikasi Email",
    )


def reset_password_page() -> HTMLResponse:
    fields = """\
<label for="password">Kata Sandi Baru</label>
    <input id="password" name="password" type="password" autocomplete="new-password" required>
    <label for="password_confirmation">Konfirmasi Kata Sandi</label>
    <input id="password_confirmation" name="password_confirmation" type="password" autocomplete="new-password" required>"""
    return _page(
        "Atur ulang kata sandi",
        "Buat kata sandi baru untuk akun kamu, minimal 8 karakter.",
        "Simpan Kata Sandi",
        fields,
    )
