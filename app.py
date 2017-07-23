#! usr/bin/env python3

import io
import os
import re
import sys
import json
import subprocess
import requests
import ipaddress
from flask import Flask, request, abort

app = Flask(__name__)


def get_github_ips():
    """Gets the ipaddress used by github to send webhooks"""
    return requests.get('https://api.github.com/meta').json()['hooks']


@app.route("/")
def index():
    # Checks if the ip is in the github ip ranges.
    for block in get_github_ips():
        ip = ipaddress.ip_address(u'%s' % request.remote_addr)
        if ipaddress.ip_address(ip) in ipaddress.ip_network(block):
            break
    else:
        abort(403)

    if request.headers.get('X-GitHub-Event') == "ping":
        return json.dumps({'msg': 'Hi!'})
    if request.headers.get('X-GitHub-Event') != "push":
        return json.dumps({'msg': "wrong event type"})

    repos = json.loads(io.open('repos.json', 'r').read())
    payload = json.loads(request.data)

    repo_meta = {
        'name': payload['repository']['name'],
        'owner': payload['repository']['owner']['name'],
    }

    match = re.match(r"refs/heads/(?P<branch>.*)", payload['ref'])
    repo = None

    if match:
        repo_meta['branch'] = match.groupdict()['branch']
        repo = repos.get('{owner}/{name}/branch:{branch}'.format(**repo_meta),
                         None)
    if not repo:
        repo = repos.get('{owner}/{name}'.format(**repo_meta), None)

    if repo and repo.get('path', None):
        if repo.get('action', None):
            for action in repo['action']:
                subprocess.Popen(action, cwd=repo['path'])
        else:
            subprocess.Popen(
                ["git", "pull", "origin", "master"], cwd=repo['path'])
    return 'OK'


if __name__ == "__main__":
    app.run()
