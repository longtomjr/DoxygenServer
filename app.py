#! usr/bin/env python3

import io
import os
import re
import sys
import json
import subprocess
import requests
import ipaddress
import hmac
from hashlib import sha1
from flask import Flask, request, abort

app = Flask(__name__)

#if os.environ.get('USE_PROXYFIX', None) == 'true':
from werkzeug.contrib.fixers import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app)

print("EnvSecret = " + os.environ.get('SECRET', None))

@app.route("/", methods=['POST', 'GET'])
def index():
    if request.method == 'GET':
        return 'OK'
    elif request.method == 'POST':
        # Store the IP address of the requester
        request_ip = ipaddress.ip_address(u'{0}'.format(request.remote_addr))

        print(ipaddress.ip_address(request_ip))

        hook_blocks = requests.get('https://api.github.com/meta').json()[
            'hooks']

        # Check if the POST request is from github.com or GHE
        for block in hook_blocks:
            if ipaddress.ip_address(request_ip) in ipaddress.ip_network(block):
                break  # the remote_addr is within the network range of github.
        else:
            if str(request_ip) != '127.0.0.1':
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

    if match:
        repo_meta['branch'] = match.groupdict()['branch']
        repo = repos.get('{owner}/{name}/branch:{branch}'.format(**repo_meta),
                         None)
        if not repo:
            repo = repos.get('{owner}/{name}'.format(**repo_meta), None)

        if repo and repo.get('path', None):
            # Check if POST request signature is valid
            key = repo.get('key', None)
            if key:
                signature = request.headers.get('X-Hub-Signature').split('=')[
                    1]
                if type(key) == str:
                    key = key.encode()
                mac = hmac.new(key, msg=request.data, digestmod=sha1)
                if not hmac.compare_digest(mac.hexdigest(), signature):
                    abort(403)

        if repo.get('action', None):
            for action in repo['action']:
                subp = subprocess.Popen(action, cwd=repo.get('path', '.'))
                subp.wait()

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
