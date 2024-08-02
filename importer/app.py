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
LOCAL_NS_SERVER = '0-175-Bind9-DNS01'
NS_RECORDS = ['0-175-Bind9-DNS01', '0-176-Bind9-DNS02']
NS_A_RECORDS = {'0-175-Bind9-DNS01': '10.248.0.175', '0-176-Bind9-DNS02': '10.248.0.176'}

def clone_repo():
    if os.path.exists(LOCAL_REPO_DIR):
        shutil.rmtree(LOCAL_REPO_DIR)
    subprocess.check_call(['git', 'clone', REPO_URL, LOCAL_REPO_DIR])
    print("Repository cloned.")

def parse_domains():
    domains = {}
    for root, _, files in os.walk(LOCAL_REPO_DIR):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    for line in f:
                        if line.strip() and not line.startswith('#'):
                            clean_line = re.sub(r'^[\*\.]+', '', line).strip()
                            domain_parts = clean_line.split('.')
                            if len(domain_parts) > 2:
                                base_domain = '.'.join(domain_parts[-2:])
                                if base_domain not in domains:
                                    domains[base_domain] = set()
                                domains[base_domain].add(clean_line)
                            else:
                                if clean_line not in domains:
                                    domains[clean_line] = set()
                                domains[clean_line].add(clean_line)
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
        else:
            print(f"Error fetching current domains: {response.text}")
    except requests.exceptions.RequestException as e:
        print("An error occurred while getting current domains:", e)
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
        else:
            print(f"Error fetching current records for domain {domain_uuid}: {response.text}")
    except requests.exceptions.RequestException as e:
        print("An error occurred while getting current records:", e)
    return {}

def add_primary_domain(domain):
    data = {
        'domain': {
            'domainname': domain,
            'type': 'primary',
            'dnsserver': LOCAL_NS_SERVER,
            'mailadmin': 'admin.' + domain,
            'ttl': 86400,
            'refresh': 21600,
            'retry': 3600,
            'expire': 3542400,
            'negative': 3600
        }
    }
    response = requests.post(
        OPNSENSE_URL + 'domain/addPrimaryDomain',
        verify=False,
        auth=HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET),
        json=data
    )
    print(f"Request data for domain {domain}: {data}")
    print(f"Response status code: {response.status_code}")
    print(f"Response content: {response.text}")
    
    if response.status_code == 200:
        result = response.json()
        if 'uuid' in result:
            print(f"Domain {domain} created successfully with UUID: {result['uuid']}")
            for ns in NS_RECORDS:
                add_record(result['uuid'], '', 'NS', ns)
            for ns, ip in NS_A_RECORDS.items():
                add_record(result['uuid'], ns, 'A', ip)
            return result['uuid']
        else:
            print(f"Unexpected response structure while creating domain {domain}: {result}")
    else:
        print(f"Failed to create domain {domain}: {response.text}")
    return None

def add_record(domain_uuid, name, record_type, value):
    data = {
        'record': {
            'domain': domain_uuid,
            'name': name,
            'type': record_type,
            'value': value
        }
    }
    response = requests.post(
        OPNSENSE_URL + 'record/addRecord',
        verify=False,
        auth=HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET),
        json=data
    )
    print(f"Request data for record {name}: {data}")
    print(f"Response status code: {response.status_code}")
    print(f"Response content: {response.text}")
    
    if response.status_code != 200:
        print(f"Failed to add record {name}.{domain_uuid}: {response.text}")
    else:
        print(f"Record {name} added to domain {domain_uuid} successfully.")
    return response.status_code == 200

def delete_all_domains():
    current_domains = get_current_domains()
    for domain_name, domain_details in current_domains.items():
        delete_domain(domain_details['uuid'])

def delete_domain(domain_uuid):
    response = requests.post(
        OPNSENSE_URL + 'domain/delDomain',
        verify=False,
        auth=HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET),
        json={'uuid': domain_uuid}
    )
    if response.status_code != 200:
        print(f"Failed to delete domain {domain_uuid}: {response.text}")
    else:
        print(f"Domain {domain_uuid} deleted successfully.")
    return response.status_code == 200

def reconfigure_bind():
    reconfigure_url = f'https://{OPNSENSE_IP}/api/bind/service/reconfigure'
    auth = HTTPBasicAuth(OPNSENSE_API_KEY, OPNSENSE_API_SECRET)
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(reconfigure_url, auth=auth, headers=headers, verify=False)
        if response.status_code == 200:
            print('BIND DNS successfully reconfigured')
        else:
            print(f'Error reconfiguring BIND DNS: {response.text}')
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

def update_domains(server_ip):
    clone_repo()
    domains = parse_domains()
    current_domains = get_current_domains()
    results = {}

    for domain, subdomains in domains.items():
        if domain in current_domains:
            domain_uuid = current_domains[domain]['uuid']
        else:
            domain_uuid = add_primary_domain(domain)
        
        if domain_uuid:
            for subdomain in subdomains:
                sub_name = subdomain.replace(f".{domain}", "")
                success = add_record(domain_uuid, sub_name, 'A', server_ip)
                results[subdomain] = 'Added' if success else f'Failed to add: {subdomain}'
        else:
            results[domain] = f'Failed to create domain: {domain}'

    # Reconfigure and restart BIND after adding domains
    reconfigure_bind()
    restart_bind()
    
    return render_template('update_results.html', results=results)

@app.route('/', methods=['GET', 'POST'])
def handle_request():
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'update_domains':
            server_ip = request.form.get('auto_ip', '')
            return update_domains(server_ip)
        elif action == 'restart_unbound':
            return restart_bind()
        elif action == 'delete_all_domains':
            delete_all_domains()
            return render_template('success.html', message='All domains have been deleted.')
        else:
            domain_name = request.form.get('domain_name', None)
            server_ip = request.form.get('manual_ip', None)
            if domain_name and server_ip:
                domain = domain_name.split('.')[-2] + '.' + domain_name.split('.')[-1]
                subdomain = domain_name.replace(f".{domain}", "")
                domain_uuid = add_primary_domain(domain)
                if domain_uuid:
                    success = add_record(domain_uuid, subdomain, 'A', server_ip)
                    message = f'DNS override added: {domain_name} with IP {server_ip}' if success else f'Error: Could not add record.'
                else:
                    message = f'Error: Could not create domain {domain}.'
                return render_template('success.html', message=message)

    current_domains = get_current_domains()
    return render_template('home.html', overrides=current_domains)

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
