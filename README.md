# OPNsense Unbound importer

Phyton Script welches die Domains aus dem Cache-Domain Repo als .txt Datein herunterlädt, alle .txt Datein durchsucht, alle zeilen mit 
```
"#" entfernt 
"."
"*"
"*." 
```
am anfang jeder Domain entfernt, dann vorhandene Domain Overrides auf der OPNsense ausliest, diese mit dem aus dem Repo vergleicht und anpasst oder hinzufügt.

Man kann auch manuelle Domain Overrides hinzufügen, diese werden auch mit den vorhandenen Overrides auf der OPNsense verglichen, hinzugefügt oder angepasst.

## Getting started

docker compose

```
---

services:
  unbound-importer:
    image: registry.gitlab.com/netsession1/dns/opnsense-domain-importer-unbound/importer-main:latest
    restart: always
    ports:
      - 5000:5000
    environment:
     - OPNSENSE_IP=
     - OPNSENSE_API_KEY=
     - OPNSENSE_API_SECRET=

```