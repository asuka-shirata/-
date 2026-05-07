import http.server
import os
import json
import urllib.request
import urllib.parse
from html.parser import HTMLParser

os.chdir("/Users/m0224/Desktop/ClaudeCode勉強会")


def load_env(path=".env"):
    """シンプルな .env ファイルローダー"""
    env = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return env


class OGPParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og = {}
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "meta":
            d = dict((k.lower(), v or "") for k, v in attrs)
            prop = d.get("property", d.get("name", ""))
            content = d.get("content", "")
            if prop and content:
                if prop.startswith("og:"):
                    self.og[prop[3:]] = content
                elif prop == "description" and "description" not in self.og:
                    self.og["description"] = content
        elif tag == "title":
            self._in_title = True

    def handle_data(self, data):
        if self._in_title:
            self.title += data

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._in_title = False


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/meta":
            self._handle_meta(parsed.query)
        elif parsed.path == "/api/weather":
            self._handle_weather()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/proxy/anthropic":
            self._handle_anthropic()
        elif parsed.path == "/api/slack":
            self._handle_slack()
        else:
            self.send_error(404)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_meta(self, query):
        params = urllib.parse.parse_qs(query)
        url = params.get("url", [""])[0]
        if not url:
            self._json_response({"error": "url parameter required"}, 400)
            return
        try:
            if "youtube.com" in url or "youtu.be" in url:
                oembed = "https://www.youtube.com/oembed?url=" + urllib.parse.quote(url) + "&format=json"
                req = urllib.request.Request(oembed, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read().decode("utf-8"))
                vid = ""
                if "v=" in url:
                    vid = url.split("v=")[1].split("&")[0]
                elif "youtu.be/" in url:
                    vid = url.split("youtu.be/")[1].split("?")[0]
                self._json_response({
                    "title": data.get("title", ""),
                    "description": data.get("author_name", "") + " の動画",
                    "image": "https://img.youtube.com/vi/" + vid + "/mqdefault.jpg" if vid else "",
                    "source": "YouTube",
                })
                return

            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            })
            with urllib.request.urlopen(req, timeout=8) as r:
                content = r.read(65536).decode("utf-8", errors="ignore")
            hostname = urllib.parse.urlparse(url).hostname or ""
            parser = OGPParser()
            parser.feed(content)
            self._json_response({
                "title": parser.og.get("title") or parser.title.strip(),
                "description": parser.og.get("description", ""),
                "image": parser.og.get("image", ""),
                "source": hostname.replace("www.", ""),
            })
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _handle_anthropic(self):
        try:
            body = self._read_body()
            data = json.loads(body.decode("utf-8"))
            api_key = data.pop("_apiKey", "")
            if not api_key:
                self._json_response({"error": "APIキーが設定されていません"}, 400)
                return

            has_web_search = any(
                "web_search" in str(t.get("type", ""))
                for t in data.get("tools", [])
            )
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            if has_web_search:
                headers["anthropic-beta"] = "web-search-2025-03-05"

            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(data).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    resp_body = r.read()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
            except urllib.error.HTTPError as e:
                err_body = e.read()
                self.send_response(e.code)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_body)))
                self.end_headers()
                self.wfile.write(err_body)
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _handle_weather(self):
        env = load_env()
        api_key = env.get("OPENWEATHER_API_KEY", "")
        if not api_key:
            self._json_response({"error": ".env に OPENWEATHER_API_KEY が設定されていません"}, 400)
            return
        try:
            url = (
                "https://api.openweathermap.org/data/2.5/weather"
                f"?q=Tokyo,JP&appid={api_key}&units=metric&lang=ja"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
            self._json_response(data)
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="ignore")
            self._json_response({"error": f"OpenWeatherMap APIエラー ({e.code}): {err}"}, e.code)
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _handle_slack(self):
        try:
            body = self._read_body()
            data = json.loads(body.decode("utf-8"))
            webhook_url = data.pop("_webhookUrl", "")
            if not webhook_url:
                self._json_response({"error": "Webhook URLが設定されていません"}, 400)
                return
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                r.read()
            self._json_response({"ok": True})
        except Exception as e:
            self._json_response({"error": str(e)}, 500)


httpd = http.server.HTTPServer(("", 3456), Handler)
print("サーバー起動中: http://localhost:3456/catchup-dashboard.html")
httpd.serve_forever()
