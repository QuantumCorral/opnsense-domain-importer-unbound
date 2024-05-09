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
    if response.status_code != 200:
        print("Error fetching files:", response.status_code, response.text)
        return []
    return [file['download_url'] for file in response.json() if file['name'].endswith('.txt')]

def parse_domains(files):
    domains = set()
    for file_url in files:
        response = requests.get(file_url)
        if response.status_code != 200:
            continue
        for line in response.text.splitlines():
            if line.strip() and not line.startswith('#'):
                clean_line = re.sub(r'\*|\.|;|#.*', '', line).strip()
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
        <button type="submit" name="action" value="download_and_override">Download Domains and Override</button>
    </form>
    ''')

@app.route('/', methods=['POST'])
def add_override():
    action = request.form.get('action', '')
    if action == 'download_and_override':
        return download_and_override()
    domain_name = request.form['domain_name']
    server_ip = request.form['server_ip']
    result = add_dns_override(domain_name, server_ip)
    return f'<h1>DNS Override hinzugefügt: {result}</h1>'

def download_and_override():
    files = get_github_files()
    if not files:
        return "Error: No domain files found."
    domains = parse_domains(files)
    results = {}
    for domain in domains:
        response = add_dns_override(domain, "IP_ADDRESS")  # Define IP_ADDRESS appropriately
        results[domain] = 'Success' if response.get('status') == 'ok' else 'Failed'
    return f'<h1>{len(domains)} Domains wurden hinzugefügt. Details: {results}</h1>'

def add_dns_override(domain, ip_address):
    auth = HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
    headers = {'Content-Type': 'application/json'}
    data = {
        'domain': {
            'domain': domain,
            'server': ip_address
        }
    }
    response = requests.post(OPNSENSE_URL, auth=auth, headers=headers, json=data, verify=False)
    return response.json()

if __name__ == '__main__':
    app.run(debug=True)
