from flask import Flask, request, render_template
import requests
from requests.auth import HTTPBasicAuth
import re
import subprocess
import shutil
import os
import json

app = Flask(__name__, static_folder='static')

OPNSENSE_API_KEY = os.getenv('OPNSENSE_API_KEY')
OPNSENSE_API_SECRET = os.getenv('OPNSENSE_API_SECRET')
OPNSENSE_IP = os.getenv('OPNSENSE_IP')
OPNSENSE_URL = f'https://{OPNSENSE_IP}/api/bind/'
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

def get_current_domains():
    try:
        response = requests.get(
            OPNSENSE_URL + 'domain/searchPrimaryDomain',
            verify=False,
            auth=HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
        )
        if response.status_code == 200:
            data = response.json()
            return {item['domainname']: item for item in data.get('rows', [])}
    except requests.exceptions.RequestException as e:
        print("An error occurred:", e)
    return {}

def get_current_records(domain_uuid):
    try:
        response = requests.get(
            OPNSENSE_URL + f'record/searchRecord?domain={domain_uuid}',
            verify=False,
            auth=HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
        )
        if response.status_code == 200:
            data = response.json()
            return {item['name']: item for item in data.get('rows', [])}
    except requests.exceptions.RequestException as e:
        print("An error occurred:", e)
    return {}

def add_primary_domain(domain):
    data = {'domain': {'domainname': domain, 'type': 'primary'}}
    response = requests.post(
        OPNSENSE_URL + 'domain/addPrimaryDomain',
        verify=False,
        auth=HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET),
        json=data
    )
    if response.status_code == 200:
        return response.status_code == 200, response.json()
    else:
        print(f"Error adding primary domain: {response.text}")
        return False, response.text

def add_record(domain_uuid, name, ip_address):
    data = {'record': {'domain': domain_uuid, 'name': name, 'type': 'A', 'value': ip_address}}
    response = requests.post(
        OPNSENSE_URL + 'record/addRecord',
        verify=False,
        auth=HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET),
        json=data
    )
    return response.status_code == 200, response.json()

@app.route('/', methods=['GET', 'POST'])
def handle_request():
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'update_domains':
            server_ip = request.form.get('auto_ip', '')
            return update_domains(server_ip)
        elif action == 'restart_bind':
            return restart_bind()
        else:
            return "Invalid action", 400

    current_overrides = get_current_domains()
    return render_template('home.html', overrides=current_overrides)

def update_domains(server_ip):
    clone_repo()
    domains = parse_domains()
    current_domains = get_current_domains()
    results = {}

    for domain in domains:
        main_domain = '.'.join(domain.split('.')[-2:])
        subdomain = domain[:-len(main_domain)].rstrip('.')
        if main_domain not in current_domains:
            success, response = add_primary_domain(main_domain)
            if success:
                domain_uuid = response.get('uuid')
                if not domain_uuid:
                    results[domain] = f'Failed to add domain: {response}'
                    continue
                success, response = add_record(domain_uuid, subdomain, server_ip)
                results[domain] = 'Added' if success else f'Failed to add record: {response}'
            else:
                results[domain] = f'Failed to add domain: {response}'
        else:
            domain_uuid = current_domains[main_domain]['uuid']
            current_records = get_current_records(domain_uuid)
            if subdomain not in current_records:
                success, response = add_record(domain_uuid, subdomain, server_ip)
                results[domain] = 'Added' if success else f'Failed to add record: {response}'
            else:
                results[domain] = 'Already exists'

    reconfigure_bind()
    return render_template('update_results.html', results=results)

def reconfigure_bind():
    response = requests.post(
        OPNSENSE_URL + 'service/reconfigure',
        verify=False,
        auth=HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
    )
    return response.status_code == 200

def restart_bind():
    response = requests.post(
        OPNSENSE_URL + 'service/restart',
        verify=False,
        auth=HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
    )
    return "BIND restarted successfully." if response.status_code == 200 else "Failed to restart BIND.", response.status_code

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
