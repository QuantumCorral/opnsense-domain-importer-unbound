import requests
from requests.auth import HTTPBasicAuth
import re
import subprocess
import shutil
import os
import json
from flask import Flask, request, render_template

app = Flask(__name__, static_folder='static')

OPNSENSE_API_KEY = os.getenv('OPNSENSE_API_KEY')
OPNSENSE_API_SECRET = os.getenv('OPNSENSE_API_SECRET')
OPNSENSE_IP = os.getenv('OPNSENSE_IP')
OPNSENSE_URL = f'https://{OPNSENSE_IP}/api/bind/settings/'
OPNSENSE_URL_GET = f'https://{OPNSENSE_IP}/api/bind/settings/get'
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
            domains_data = data.get('bind', {}).get('domains', {}).get('domain', {})
            if isinstance(domains_data, dict):
                return {detail.get('domainname', 'No domain info'): detail.get('type', 'No type info')
                        for detail in domains_data.values()}
            else:
                return {}
    except requests.exceptions.RequestException as e:
        print("An error occurred:", e)
    return {}

@app.route('/', methods=['GET', 'POST'])
def handle_request():
    unbound_status_info = unbound_status()
    unbound_running = unbound_status_info.get('data', {}).get('status', 'unknown')

    if request.method == 'POST':
        action = request.form.get('action', '')
        current_overrides = get_current_overrides()

        if action == 'update_domains':
            server_ip = request.form.get('auto_ip', '')
            return update_domains(server_ip)
        elif action == 'restart_unbound':
            return restart_bind()
        elif action == 'delete_all_domains':
            return delete_all_domains()
        else:
            domain_name = request.form.get('domain_name', None)
            server_ip = request.form.get('manual_ip', None)
            if domain_name and server_ip:
                if domain_name in current_overrides:
                    if current_overrides[domain_name] == server_ip:
                        message = f'No change necessary: {domain_name} already has the IP {server_ip}.'
                        return render_template('success.html', message=message)
                    else:
                        success, result = update_dns_override(domain_name, server_ip)
                        message = f'DNS override updated: {domain_name} to IP {server_ip}' if success else f'Error: {result}'
                else:
                    success, result = add_dns_override(domain_name, server_ip)
                    message = f'DNS override added: {domain_name} with IP {server_ip}' if success else f'Error: {result}'
                return render_template('success.html', message=message)

    current_overrides = get_current_overrides()
    return render_template('home.html', overrides=current_overrides, unbound_running=unbound_running)

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
    
    # Reconfigure and restart BIND after adding domains
    reconfigure_bind()
    restart_bind()
    
    return render_template('update_results.html', results=results)

def add_dns_override(domain, ip_address):
    auth = HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
    headers = {'Content-Type': 'application/json'}
    data = {'domain': {'domainname': domain, 'type': 'primary', 'dnsserver': '0-175-Bind9-DNS01.ns.lcl', 'mailadmin': 'admin.' + domain, 'ttl': 86400, 'refresh': 21600, 'retry': 3600, 'expire': 3542400, 'negative': 3600}}
    response = requests.post(OPNSENSE_URL + "addPrimaryDomain", auth=auth, headers=headers, json=data, verify=False)
    return response.status_code == 200, response.json()

def get_domain_uuid(domain):
    response = requests.get(
        OPNSENSE_URL_GET,
        verify=False,
        auth=HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
    )
    data = response.json()
    for uuid, details in data.get('bind', {}).get('domains', {}).get('domain', {}).items():
        if details.get('domainname') == domain:
            return uuid
    return None

def update_dns_override(domain, ip_address):
    uuid = get_domain_uuid(domain)
    if uuid:
        auth = HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
        headers = {'Content-Type': 'application/json'}
        data = json.dumps({'domain': {'domainname': domain, 'type': 'primary', 'dnsserver': '0-175-Bind9-DNS01.ns.lcl', 'mailadmin': 'admin.' + domain, 'ttl': 86400, 'refresh': 21600, 'retry': 3600, 'expire': 3542400, 'negative': 3600}})
        url = OPNSENSE_URL + f"setDomain/{uuid}"
        response = requests.post(url, auth=auth, headers=headers, data=data, verify=False)
        return response.status_code == 200, response.json()
    return False, "UUID not found for domain"

def reconfigure_bind():
    reconfigure_url = f'https://{OPNSENSE_IP}/api/bind/service/reconfigure'
    auth = HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(reconfigure_url, auth=auth, headers=headers, verify=False)
        if response.status_code == 200:
            print('BIND DNS successfully reconfigured')
        else:
            print(f'Failed to reconfigure BIND DNS: {response.text}')
    except Exception as e:
        print(f'Error reconfiguring BIND DNS: {str(e)}')

@app.route('/restart-bind', methods=['POST'])
def restart_bind():
    restart_url = f'https://{OPNSENSE_IP}/api/bind/service/restart'
    auth = HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(restart_url, auth=auth, headers=headers, json={}, verify=False)
        if response.status_code == 200:
            return render_template('success.html', message='BIND DNS successfully restarted')
        else:
            return render_template('error.html', message=f'Failed to restart BIND DNS: {response.text}')
    except Exception as e:
        return render_template('error.html', message=str(e))

def delete_all_domains():
    try:
        current_overrides = get_current_overrides()
        for domain in current_overrides.keys():
            uuid = get_domain_uuid(domain)
            if uuid:
                auth = HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
                headers = {'Content-Type': 'application/json'}
                url = OPNSENSE_URL + f"delDomain/{uuid}"
                response = requests.post(url, auth=auth, headers=headers, verify=False)
                if response.status_code != 200:
                    return render_template('error.html', message=f'Failed to delete domain {domain}: {response.text}')
        
        # Reconfigure and restart BIND after deleting domains
        reconfigure_bind()
        restart_bind()
        
        return render_template('success.html', message='All domains successfully deleted')
    except Exception as e:
        return render_template('error.html', message=str(e))

@app.route('/unbound-status', methods=['GET'])
def unbound_status():
    status_url = f'https://{OPNSENSE_IP}/api/bind/service/status'
    auth = HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)

    try:
        response = requests.get(status_url, auth=auth, verify=False)
        if response.status_code == 200:
            status_data = response.json()
            return {'status': 'success', 'message': 'BIND DNS status retrieved successfully', 'data': status_data}
        else:
            return {'status': 'error', 'message': f'Failed to retrieve BIND DNS status: {response.text}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
