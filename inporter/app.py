from flask import Flask, request, render_template
import requests
from requests.auth import HTTPBasicAuth
import re
import subprocess
import shutil
import os
import json

app = Flask(__name__)

OPNSENSE_API_KEY = 'CtNv6Nw5iE4Tg6CGfNdkSM/3/XvRTrM09BGEPr75+Pq2Aue7hLpMxTn2iVZ4MqKW6UWRuEvQ+Ln34RyZ'
OPNSENSE_API_SECRET = 'dsNfsP99QHxYoFuBrZU6U3JXB0xuAFZnTr84qhgIWj7B+UB25DeMIZoOf2uVuiVBI6n8ezFVi/YiIdGp'
OPNSENSE_URL = 'https://10.22.30.114/api/unbound/settings/'
OPNSENSE_URL_GET = 'https://10.22.30.114/api/unbound/settings/get'
REPO_URL = "https://github.com/uklans/cache-domains.git"
LOCAL_REPO_DIR = "/opt/download"

def clone_repo():
    if os.path.exists(LOCAL_REPO_DIR):
        shutil.rmtree(LOCAL_REPO_DIR)
    subprocess.check_call(['git', 'clone', REPO_URL, LOCAL_REPO_DIR])
    print("Repository cloned.")

def parse_domains():
    domains = set()
    for root, _, files in os.walk(LOCAL_REPO_DIR):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    for line in f:
                        if line.strip() and not line.startswith('#'):
                            clean_line = re.sub(r'^[\*\.]+', '', line).strip()
                            domains.add(clean_line)
    return domains

def get_current_overrides():
    try:
        response = requests.get(
            OPNSENSE_URL_GET,
            verify=False,
            auth=HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
        )
        if response.status_code == 200:
            data = response.json()
            domains_data = data.get('unbound', {}).get('domains', {}).get('domain', {})
            if isinstance(domains_data, dict):
                return {detail.get('domain', 'No domain info'): detail.get('server', 'No server info')
                        for detail in domains_data.values()}
            else:
                return {}
    except requests.exceptions.RequestException as e:
        print("An error occurred:", e)
    return {}


@app.route('/', methods=['GET', 'POST'])
def handle_request():
    if request.method == 'POST':
        action = request.form.get('action', '')
        domain_name = request.form['domain_name']
        server_ip = request.form['manual_ip']

        if action == 'update_domains':
            return update_domains(server_ip)

        current_overrides = get_current_overrides()
        # Überprüfe, ob die Domain bereits existiert und handle entsprechend
        if domain_name in current_overrides:
            if current_overrides[domain_name] == server_ip:
                message = f'Keine Änderung notwendig: {domain_name} hat bereits die IP {server_ip}.'
                return render_template('success.html', message=message)
            else:
                # Update vorhandene Domain-Override
                success, result = update_dns_override(domain_name, server_ip)
                message = f'DNS Override aktualisiert: {domain_name} auf IP {server_ip}' if success else f'Fehler: {result}'
        else:
            # Füge eine neue Domain-Override hinzu
            success, result = add_dns_override(domain_name, server_ip)
            message = f'DNS Override hinzugefügt: {domain_name} mit IP {server_ip}' if success else f'Fehler: {result}'

        return render_template('success.html', message=message)

    current_overrides = get_current_overrides()
    return render_template('home.html', overrides=current_overrides)

def update_domains(server_ip):
    clone_repo()
    domains = parse_domains()
    current_overrides = get_current_overrides()
    results = {}
    for domain in domains:
        if domain in current_overrides and current_overrides[domain] != server_ip:
            success, response = update_dns_override(domain, server_ip)
            results[domain] = 'Updated' if success else f'Failed to update: {response}'
        elif domain not in current_overrides:
            success, response = add_dns_override(domain, server_ip)
            results[domain] = 'Added' if success else f'Failed to add: {response}'
    return render_template('update_results.html', results=results)


def add_dns_override(domain, ip_address):
    auth = HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
    headers = {'Content-Type': 'application/json'}
    data = {'domain': {'domain': domain, 'server': ip_address}}
    response = requests.post(OPNSENSE_URL + "addDomainOverride", auth=auth, headers=headers, json=data, verify=False)
    return response.status_code == 200, response.json()

def get_domain_uuid(domain):
    response = requests.get(
        OPNSENSE_URL_GET,
        verify=False,
        auth=HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
    )
    data = response.json()
    for uuid, details in data.get('unbound', {}).get('domains', {}).get('domain', {}).items():
        if details.get('domain') == domain:
            return uuid
    return None

def update_dns_override(domain, ip_address):
    uuid = get_domain_uuid(domain)
    if uuid:
        auth = HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
        headers = {'Content-Type': 'application/json'}
        data = json.dumps({'domain': {'domain': domain, 'server': ip_address}})
        url = OPNSENSE_URL + f"setDomainOverride/{uuid}"
        response = requests.post(url, auth=auth, headers=headers, data=data, verify=False)
        return response.status_code == 200, response.json()
    return False, "UUID not found for domain"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
