#!/usr/bin/env python3
import os
import re
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote

PORT = int(os.environ.get('PORT', '8080'))
GITHUB_RAW = "https://raw.githubusercontent.com/ananthlk/Mobius-Master/main/docs"
SPEC_DIR = os.path.dirname(os.path.abspath(__file__))

def escape_html(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')

def markdown_to_html(md_text):
    """Simple markdown to HTML converter for spec docs."""
    lines = md_text.split('\n')
    html_lines = []
    in_code_block = False
    in_list = False
    code_fence_lang = None

    for line in lines:
        # Code fences
        if line.startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_fence_lang = line[3:].strip() or 'text'
                html_lines.append(f'<pre class="code-block"><code class="language-{escape_html(code_fence_lang)}">')
            else:
                in_code_block = False
                html_lines.append('</code></pre>')
            continue

        if in_code_block:
            html_lines.append(escape_html(line) + '\n')
            continue

        # Headings
        if line.startswith('### '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h3>{escape_html(line[4:])}</h3>')
            continue
        elif line.startswith('## '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h2>{escape_html(line[3:])}</h2>')
            continue
        elif line.startswith('# '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h1>{escape_html(line[2:])}</h1>')
            continue

        # Lists
        if line.startswith('- ') or line.startswith('* '):
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            item_text = line[2:].strip()
            html_lines.append(f'<li>{escape_html(item_text)}</li>')
            continue
        elif in_list and line.strip() == '':
            html_lines.append('</ul>')
            in_list = False

        # Inline code and bold/italic
        if line.strip():
            # Simple inline markdown
            line = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', line)
            line = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', line)
            line = re.sub(r'`([^`]+)`', r'<code>\1</code>', line)
            html_lines.append(f'<p>{line}</p>')
        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            else:
                html_lines.append('<br>')

    if in_list:
        html_lines.append('</ul>')
    if in_code_block:
        html_lines.append('</code></pre>')

    return '\n'.join(html_lines)

def render_spec_reader(title, md_content):
    """Render markdown spec in a styled reader view."""
    html_content = markdown_to_html(md_content)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape_html(title)} — Mobius Specs</title>
  <style>
    :root {{
      --primary: #7c3aed;
      --bg: #f8f7fb;
      --surface: #ffffff;
      --text: #1c1a27;
      --muted: #6b6880;
      --border: #e2dff0;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #141220;
        --surface: #1d1a2e;
        --text: #eceaf6;
        --muted: #9d99b5;
        --border: #332e4d;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
    }}
    header {{
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    header h1 {{ margin: 0; font-size: 20px; font-weight: 700; }}
    a {{ color: var(--primary); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    main {{
      max-width: 900px;
      margin: 0 auto;
      padding: 32px 24px;
    }}
    h1, h2, h3 {{ margin-top: 32px; margin-bottom: 16px; font-weight: 700; }}
    h1 {{ font-size: 32px; }}
    h2 {{ font-size: 24px; }}
    h3 {{ font-size: 18px; }}
    p {{ margin: 0 0 16px 0; }}
    ul {{ margin: 16px 0; padding-left: 24px; }}
    li {{ margin-bottom: 8px; }}
    code {{
      background: rgba(124, 58, 237, 0.1);
      color: var(--primary);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
      font-size: 0.9em;
    }}
    .code-block {{
      background: rgba(0, 0, 0, 0.05);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      overflow-x: auto;
      margin: 16px 0;
    }}
    .code-block code {{
      background: none;
      color: var(--text);
      padding: 0;
      display: block;
      font-size: 13px;
      line-height: 1.5;
    }}
    .back-link {{
      display: inline-block;
      margin-bottom: 32px;
      font-size: 14px;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escape_html(title)}</h1>
    <a href="/" class="back-link">← Back to Catalog</a>
  </header>
  <main>
    {html_content}
  </main>
</body>
</html>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Serve index.html for root — fetch from git so updates are live (no rebuild needed)
        if self.path == '/' or self.path == '':
            try:
                # Fetch from GitHub so changes are picked up without container rebuild
                github_root = GITHUB_RAW.rsplit('/', 1)[0]  # Remove /docs, use base
                index_url = f"{github_root}/specs-platform/index.html"
                with urllib.request.urlopen(index_url, timeout=5) as r:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                    self.end_headers()
                    self.wfile.write(r.read())
                return
            except Exception as e:
                # Fallback: serve local copy if git fetch fails
                try:
                    with open(os.path.join(SPEC_DIR, 'index.html'), 'rb') as f:
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html')
                        self.end_headers()
                        self.wfile.write(f.read())
                    return
                except:
                    self.send_error(500)
                    return

        # Serve specs with reader view
        if self.path.startswith('/specs/'):
            spec_path = unquote(self.path[7:])
            url = f"{GITHUB_RAW}/{spec_path}"
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    md_content = r.read().decode('utf-8')
                    title = spec_path.rsplit('/', 1)[-1].replace('-', ' ').replace('.md', '').title()
                    html = render_spec_reader(title, md_content)
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(html.encode('utf-8'))
                    return
            except:
                self.send_error(404)
                return

        self.send_error(404)
    
    def log_message(self, format, *args):
        pass  # suppress logs

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f"Server running on port {PORT}")
    server.serve_forever()
