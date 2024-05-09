from flask import Flask, request, render_template_string, redirect, url_for
import requests
from requests.auth import HTTPBasicAuth
import re
import subprocess
import shutil
import os

app = Flask(__name__)

# Ersetze mit den tatsächlichen API-Zugangsdaten und der URL deiner OPNsense-Instanz
OPNSENSE_API_KEY = 'CtNv6Nw5iE4Tg6CGfNdkSM/3/XvRTrM09BGEPr75+Pq2Aue7hLpMxTn2iVZ4MqKW6UWRuEvQ+Ln34RyZ'
OPNSENSE_API_SECRET = 'dsNfsP99QHxYoFuBrZU6U3JXB0xuAFZnTr84qhgIWj7B+UB25DeMIZoOf2uVuiVBI6n8ezFVi/YiIdGp'
OPNSENSE_URL = 'https://10.22.30.114/api/unbound/settings/addDomainOverride'
REPO_URL = "https://github.com/uklans/cache-domains.git"
LOCAL_REPO_DIR = "/tmp/cache-domains"

def clone_repo():
    if os.path.exists(LOCAL_REPO_DIR):
        shutil.rmtree(LOCAL_REPO_DIR)
    subprocess.check_call(['git', 'clone', REPO_URL, LOCAL_REPO_DIR])
    print("Repository cloned.")

def delete_repo():
    shutil.rmtree(LOCAL_REPO_DIR)
    print("Repository deleted.")

def parse_domains():
    domains = set()
    for root, _, files in os.walk(os.path.join(LOCAL_REPO_DIR, 'cache_domains')):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    for line in f:
                        if line.strip() and not line.startswith('#'):
                            clean_line = re.sub(r'\*|\.|;|#.*', '', line).strip()
                            domains.add(clean_line)
    return domains

@app.route('/', methods=['GET'])
def index():
    return render_template_string('''
    <h1>OPNsense Domain Overrides Management</h1>
    <form method="post">
        <button type="submit" name="action" value="update_domains">Update Domains</button>
    </form>
    ''')

@app.route('/', methods=['POST'])
def handle_request():
    action = request.form.get('action', '')
    if action == 'update_domains':
        return update_domains()
    return redirect(url_for('index'))

def update_domains():
    clone_repo()
    domains = parse_domains()
    results = {}
    for domain in domains:
        response = add_dns_override(domain, "IP_ADDRESS")  # Define IP_ADDRESS appropriately
        results[domain] = 'Success' if response.status_code == 200 else 'Failed'
    delete_repo()
    return f'<h1>{len(domains)} Domains wurden aktualisiert. Details: {results}</h1>'

def add_dns_override(domain, ip_address):
    auth = HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
    headers = {'Content-Type': 'application/json'}
    data = {'domain': {'domain': domain, 'server': ip_address}}
    response = requests.post(OPNSENSE_URL, auth=auth, headers=headers, json=data, verify=False)
    return response

if __name__ == '__main__':
    app.run(debug=True)
