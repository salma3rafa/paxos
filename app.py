from flask import Flask, request, jsonify
 
import os
import threading
import requests
import time
import random

app = Flask(__name__)


NODE_ID = int(os.environ['NODE_ID'])
PEERS = os.environ['PEERS'].split(',')

# Paxos state
promised_id = None
accepted_id = None
accepted_value = None
learned_value = None

majority = (len(PEERS) + 1) 

@app.route('/prepare', methods=['POST'])
def prepare():
    global promised_id
    proposal_id = request.json['proposal_id']
    if not promised_id or proposal_id > promised_id:
        promised_id = proposal_id
        return jsonify({'promise': True, 'accepted_id': accepted_id, 'accepted_value': accepted_value})
    return jsonify({'promise': False})

@app.route('/accept', methods=['POST'])
def accept():
    global promised_id, accepted_id, accepted_value
    proposal_id = request.json['proposal_id']
    value = request.json['value']
    if not promised_id or proposal_id >= promised_id:
        promised_id = proposal_id
        accepted_id = proposal_id
        accepted_value = value
        return jsonify({'accepted': True})
    return jsonify({'accepted': False})

@app.route('/learn', methods=['POST'])
def learn():
    global learned_value
    learned_value = request.json['value']
    print(f"[Node {NODE_ID}] Learned value: {learned_value}")
    return jsonify({'status': 'ok'})

def send_to_node(node, endpoint, data):
    try:
        url = f'http://{node}:5000/{endpoint}'
        res = requests.post(url, json=data, timeout=2)
        return res.json()
    except:
        return None

def propose_value(value):
    proposal_id = int(time.time() * 1000) + NODE_ID  # Unique proposal ID
    promises = []
    print(f"[Node {NODE_ID}] Starting proposal for value: {value} with id {proposal_id}")

    for peer in PEERS:
        res = send_to_node(peer, 'prepare', {'proposal_id': proposal_id})
        if res and res.get('promise'):
            promises.append(res)

    if len(promises) + 1 >= majority:
        # Use highest accepted_value if exists
        highest = max((p for p in promises if p['accepted_id']), default=None, key=lambda x: x['accepted_id'] or 0)
        if highest and highest['accepted_value']:
            value = highest['accepted_value']

        acks = []
        for peer in PEERS:
            res = send_to_node(peer, 'accept', {'proposal_id': proposal_id, 'value': value})
            if res and res.get('accepted'):
                acks.append(res)

        if len(acks) + 1 >= majority:
            # Broadcast to learners
            print(f"[Node {NODE_ID}] Consensus reached! Value: {value}")
            for peer in PEERS:
                send_to_node(peer, 'learn', {'value': value})
            learned_value = value
        else:
            print(f"[Node {NODE_ID}] Accept phase failed")
    else:
        print(f"[Node {NODE_ID}] Prepare phase failed")

@app.route('/propose', methods=['POST'])
def propose():
    value = request.json['value']
    threading.Thread(target=propose_value, args=(value,)).start()
    return jsonify({'status': 'proposal started'})

@app.route('/')
def index():
    return jsonify({
        'node': NODE_ID,
        'accepted_id': accepted_id,
        'accepted_value': accepted_value,
        'learned_value': learned_value
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
