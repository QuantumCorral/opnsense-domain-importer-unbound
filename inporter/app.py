from flask import Flask, request, render_template_string, redirect, url_for
import requests
from requests.auth import HTTPBasicAuth
import re

app = Flask(__name__)

# Ersetze mit den tatsächlichen API-Zugangsdaten und der URL deiner OPNsense-Instanz
OPNSENSE_API_KEY = 'CtNv6Nw5iE4Tg6CGfNdkSM/3/XvRTrM09BGEPr75+Pq2Aue7hLpMxTn2iVZ4MqKW6UWRuEvQ+Ln34RyZ'
OPNSENSE_API_SECRET = 'dsNfsP99QHxYoFuBrZU6U3JXB0xuAFZnTr84qhgIWj7B+UB25DeMIZoOf2uVuiVBI6n8ezFVi/YiIdGp'
OPNSENSE_URL = 'https://10.22.30.114/api/unbound/settings/addDomainOverride'

# GitHub Repo URL für Textdateien
REPO_URL = "https://api.github.com/repos/uklans/cache-domains/contents/cache_domains"

def get_github_files():
    response = requests.get(REPO_URL)
    files = [file['download_url'] for file in response.json() if file['name'].endswith('.txt')]
    return files

def parse_domains(files):
    domains = set()
    for file_url in files:
        response = requests.get(file_url)
        for line in response.text.splitlines():
            if not line.startswith('#') and line.strip():
                # Entfernen von '*' und Kommentaren
                clean_line = re.sub(r'\*|\s*#.*', '', line).strip()
                if clean_line:
                    domains.add(clean_line)
    return domains

@app.route('/', methods=['GET'])
def index():
    return render_template_string('''
    <h1>OPNsense Domain Overrides Management</h1>
    <form method="post">
        Domain Name: <input type="text" name="domain_name"><br>
        Server IP: <input type="text" name="server_ip"><br>
        <input type="submit" value="Submit"><br><br>
        <button formaction="/download-and-override">Download Domains and Override</button>
    </form>
    ''')

@app.route('/', methods=['POST'])
def add_override():
    domain_name = request.form['domain_name']
    server_ip = request.form['server_ip']
    result = add_dns_override(domain_name, server_ip)
    return f'<h1>DNS Override hinzugefügt: {result}</h1>'

@app.route('/download-and-override', methods=['POST'])
def download_and_override():
    files = get_github_files()
    domains = parse_domains(files)
    # Hier könnten Sie bestehende Einträge löschen
    for domain in domains:
        add_dns_override(domain, "IP_to_be_defined")  # Hier müssen Sie eine IP-Adresse definieren oder anpassen
    return f'<h1>{len(domains)} Domains wurden hinzugefügt.</h1>'

def add_dns_override(domain, ip_address):
    auth = HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
    headers = {'Content-Type': 'application/json'}
    data = {
        'domain': {
            'domain': domain,
            'server': ip_address
        }
    }
    response = requests.post(OPNSENSE_URL, auth=auth, headers=headers, json=data, verify=False)  # SSL-Überprüfung deaktiviert für Testzwecke
    return response.json()

if __name__ == '__main__':
    app.run(debug=True)
