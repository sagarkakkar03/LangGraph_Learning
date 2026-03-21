from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

from config import EMAIL_ADDRESSES, DEPARTMENTS
from graph import workflow

app = FastAPI(title="HR Email Routing System")


class EmailRequest(BaseModel):
    sender_email: str
    query: str


class EmailResponse(BaseModel):
    sender_email: str
    routed_from: str
    routed_to: str
    department: str
    reasoning: str
    response: str
    email_status: Optional[dict] = None


@app.post("/send", response_model=EmailResponse)
async def route_email(request: EmailRequest):
    result = workflow.invoke({
        "query": request.query,
        "sender_email": request.sender_email,
    })
    return EmailResponse(
        sender_email=request.sender_email,
        routed_from=EMAIL_ADDRESSES["main"],
        routed_to=result["target_email"],
        department=result["department"],
        reasoning=result["reasoning"],
        response=result["response"],
        email_status=result.get("email_status"),
    )


@app.get("/emails")
async def list_emails():
    return EMAIL_ADDRESSES


@app.get("/health")
async def health():
    return {"status": "healthy"}


def _build_email_chips() -> str:
    chips = [
        f'<span class="email-chip">'
        f'<span class="dot" style="background:#6c63ff"></span>'
        f'{EMAIL_ADDRESSES["main"]}</span>'
    ]
    for dept, info in DEPARTMENTS.items():
        color = info.get("color", "#999")
        chips.append(
            f'<span class="email-chip">'
            f'<span class="dot" style="background:{color}"></span>'
            f'{EMAIL_ADDRESSES[dept]}</span>'
        )
    return "\n    ".join(chips)


def _build_banner_css() -> str:
    rules = []
    for dept, info in DEPARTMENTS.items():
        color = info.get("color", "#999")
        rules.append(
            f".route-banner.{dept} {{ "
            f"background: {color}18; border-left: 4px solid {color}; }}"
        )
    return "\n  ".join(rules)


@app.get("/", response_class=HTMLResponse)
async def ui():
    email_chips = _build_email_chips()
    banner_css = _build_banner_css()
    main_email = EMAIL_ADDRESSES["main"]

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HR Email Router</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: #f0f2f5; color: #1a1a2e; min-height: 100vh;
    display: flex; justify-content: center; padding: 40px 16px;
  }}
  .container {{ width: 100%; max-width: 760px; }}
  h1 {{ font-size: 1.8rem; margin-bottom: 4px; }}
  .subtitle {{ color: #555; margin-bottom: 28px; font-size: 0.95rem; }}
  .emails-bar {{
    display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 28px;
  }}
  .email-chip {{
    background: #fff; border: 1px solid #ddd; border-radius: 20px;
    padding: 6px 14px; font-size: 0.8rem; color: #333;
    display: flex; align-items: center; gap: 6px;
  }}
  .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
  .card {{
    background: #fff; border-radius: 12px; padding: 28px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 24px;
  }}
  label {{ display: block; font-weight: 600; margin-bottom: 6px; font-size: 0.9rem; }}
  input, textarea {{
    width: 100%; padding: 10px 14px; border: 1px solid #ddd;
    border-radius: 8px; font-size: 0.95rem; font-family: inherit;
    transition: border-color 0.2s;
  }}
  input:focus, textarea:focus {{ outline: none; border-color: #6c63ff; }}
  textarea {{ resize: vertical; min-height: 120px; }}
  .field + .field {{ margin-top: 16px; }}
  button {{
    margin-top: 20px; width: 100%; padding: 12px;
    background: #6c63ff; color: #fff; border: none; border-radius: 8px;
    font-size: 1rem; font-weight: 600; cursor: pointer;
    transition: background 0.2s;
  }}
  button:hover {{ background: #5a52d5; }}
  button:disabled {{ background: #aaa; cursor: not-allowed; }}
  .result {{ display: none; }}
  .result.show {{ display: block; }}
  .route-banner {{
    display: flex; align-items: center; gap: 12px;
    padding: 14px 18px; border-radius: 8px;
    margin-bottom: 18px; font-size: 0.92rem;
  }}
  {banner_css}
  .route-banner strong {{ font-size: 0.95rem; }}
  .meta {{ font-size: 0.85rem; color: #666; margin-bottom: 14px; }}
  .email-tag {{
    display: inline-block; background: #eef; color: #6c63ff;
    padding: 2px 10px; border-radius: 12px; font-size: 0.78rem;
    margin-top: 6px;
  }}
  .response-text {{
    background: #fafafa; border: 1px solid #eee; border-radius: 8px;
    padding: 18px; white-space: pre-wrap; line-height: 1.6; font-size: 0.92rem;
  }}
  .spinner {{
    display: inline-block; width: 18px; height: 18px;
    border: 2px solid #fff; border-top-color: transparent;
    border-radius: 50%; animation: spin 0.6s linear infinite;
    vertical-align: middle; margin-right: 8px;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>
<div class="container">
  <h1>HR Email Router</h1>
  <p class="subtitle">Send a query to <strong>{main_email}</strong> &mdash; it gets routed to the right department and an email is sent automatically.</p>

  <div class="emails-bar">
    {email_chips}
  </div>

  <div class="card">
    <div class="field">
      <label for="email">Your Email</label>
      <input id="email" type="email" placeholder="you@example.com" />
    </div>
    <div class="field">
      <label for="query">Your Query</label>
      <textarea id="query" placeholder="e.g. I haven't received my pay slip for March..."></textarea>
    </div>
    <button id="sendBtn" onclick="send()">Send to HR</button>
  </div>

  <div class="result card" id="resultCard">
    <div class="route-banner" id="banner">
      <div>
        <strong id="deptLabel"></strong><br/>
        <span id="routeLabel"></span><br/>
        <span class="email-tag" id="emailTag"></span>
      </div>
    </div>
    <p class="meta" id="reasonText"></p>
    <label>Response</label>
    <div class="response-text" id="responseText"></div>
  </div>
</div>
<script>
async function send() {{
  const btn = document.getElementById('sendBtn');
  const email = document.getElementById('email').value.trim();
  const query = document.getElementById('query').value.trim();
  if (!email || !query) return alert('Please fill in both fields.');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Routing & sending...';
  document.getElementById('resultCard').classList.remove('show');
  try {{
    const res = await fetch('/send', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{sender_email: email, query}})
    }});
    const data = await res.json();
    const banner = document.getElementById('banner');
    banner.className = 'route-banner ' + data.department;
    document.getElementById('deptLabel').textContent =
      data.department.replace(/_/g, ' ').replace(/\\b\\w/g, c => c.toUpperCase());
    document.getElementById('routeLabel').textContent =
      data.routed_from + '  \\u2192  ' + data.routed_to;
    const es = data.email_status;
    const tag = document.getElementById('emailTag');
    if (es && es.reply && es.reply.success) {{
      tag.textContent = es.reply.message;
    }} else {{
      tag.textContent = 'Email delivery pending \\u2014 check SMTP config';
    }}
    document.getElementById('reasonText').textContent = data.reasoning;
    document.getElementById('responseText').textContent = data.response;
    document.getElementById('resultCard').classList.add('show');
  }} catch (e) {{
    alert('Error: ' + e.message);
  }} finally {{
    btn.disabled = false;
    btn.textContent = 'Send to HR';
  }}
}}
</script>
</body>
</html>
"""
