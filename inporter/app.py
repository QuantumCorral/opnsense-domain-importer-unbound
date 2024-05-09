from flask import Flask, request, render_template_string
import requests
import json

app = Flask(__name__)

# Ersetze mit den tatsächlichen API-Zugangsdaten und der URL deiner OPNsense-Instanz
OPNSENSE_API_KEY = 'CtNv6Nw5iE4Tg6CGfNdkSM/3/XvRTrM09BGEPr75+Pq2Aue7hLpMxTn2iVZ4MqKW6UWRuEvQ+Ln34RyZ'
OPNSENSE_API_SECRET = 'dsNfsP99QHxYoFuBrZU6U3JXB0xuAFZnTr84qhgIWj7B+UB25DeMIZoOf2uVuiVBI6n8ezFVi/YiIdGp'
OPNSENSE_URL = 'https://10.22.30.114/api'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        domain = request.form['domain']
        ip_address = request.form['ip_address']
        result = add_dns_override(domain, ip_address)
        return f'<h1>DNS Override hinzugefügt: {result}</h1>'
    return '''
    <form method="post">
        Domain: <input type="text" name="domain"><br>
        IP Address: <input type="text" name="ip_address"><br>
        <input type="submit" value="Submit">
    </form>
    '''

def add_dns_override(domain, ip_address):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPNSENSE_API_KEY}:{OPNSENSE_API_SECRET}'
    }
    data = {
        'domain': domain,
        'ip': ip_address
    }
    response = requests.post(f'{OPNSENSE_URL}/unbound/dns/override/add', headers=headers, data=json.dumps(data))
    return response.json()

if __name__ == '__main__':
    app.run(debug=True)