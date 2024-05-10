# OPNsense Unbound inporter

Phyton Script welches die Domains aus dem Cache-Domain Repo als .txt Datein herunterlädt, alle .txt Datein durchsucht, alle zeilen mit "#" entfernt, ".", "*" und "*." am anfang jeder Domain entfernt, dann vorhandene Domain Overrides auf der OPNsense ausliest, diese mit dem aus dem Repo vergleicht und anpasst oder hinzufügt.

Man kann auch manuelle Domain Overrides hinzufügen, diese werden auch mit den vorhandenen Overrides auf der OPNsense verglichen, hinzugefügt oder angepasst.

## Getting started

docker compose

```
---

services:
  unbound-importer:
    image: registry.gitlab.com/dns61418/opnsense-unbound-inporter/inporter-main
    restart: always
    ports:
      - 5000:5000
    environment:
     - OPNsense_IP=
     - OPNsense_API_KEY=
     - OPNSENSE_API_SECRET=

```