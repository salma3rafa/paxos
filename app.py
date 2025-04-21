from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

class PaxosNode:
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers
        self.promised_id = None
        self.accepted_id = None
        self.accepted_value = None
        self.proposal_id = 0
        self.learned_value = None

    def prepare(self, proposal_id):
        if self.promised_id is None or proposal_id > self.promised_id:
            self.promised_id = proposal_id
            return True, self.accepted_id, self.accepted_value
        return False, self.accepted_id, self.accepted_value

    def accept(self, proposal_id, value):
        if self.promised_id is None or proposal_id >= self.promised_id:
            self.promised_id = proposal_id
            self.accepted_id = proposal_id
            self.accepted_value = value
            return True
        return False

    def learn(self, value):
        self.learned_value = value

    def propose(self, value):
        self.proposal_id += 1
        proposal_id = self.proposal_id
        promises = 0
        accepted_values = []

        for peer in self.peers:
            try:
                res = requests.post(f"http://{peer}/prepare", json={'proposal_id': proposal_id})
                if res.status_code == 200 and res.json().get('promise'):
                    promises += 1
                    accepted = res.json()
                    if accepted.get('accepted_value') is not None:
                        accepted_values.append(accepted['accepted_value'])
            except Exception as e:
                print(f"Prepare request to {peer} failed: {e}")

        if promises <= len(self.peers) // 2:
            return False

        if accepted_values:
            value = accepted_values[0]

        accepts = 0
        for peer in self.peers:
            try:
                res = requests.post(f"http://{peer}/accept", json={'proposal_id': proposal_id, 'value': value})
                if res.status_code == 200 and res.json().get('accepted'):
                    accepts += 1
            except Exception as e:
                print(f"Accept request to {peer} failed: {e}")

        if accepts > len(self.peers) // 2:
            for peer in self.peers:
                try:
                    requests.post(f"http://{peer}/learn", json={'value': value})
                except Exception as e:
                    print(f"Learn request to {peer} failed: {e}")
            self.learn(value)
            return True

        return False

# Get node ID and peers from environment
node_id = int(os.getenv("NODE_ID", 1))
peers_env = os.getenv("PEERS", "")
peers = [f"{peer}:5000" for peer in peers_env.split(",") if peer]

node = PaxosNode(node_id, peers)

@app.route("/")
def home():
    return jsonify({
        "node_id": node.node_id,
        "learned_value": node.learned_value
    })

@app.route("/propose", methods=["POST"])
def propose():
    value = request.json.get("value")
    success = node.propose(value)
    return jsonify({"success": success})

@app.route("/prepare", methods=["POST"])
def prepare():
    proposal_id = request.json.get("proposal_id")
    promise, accepted_id, accepted_value = node.prepare(proposal_id)
    return jsonify({
        "promise": promise,
        "accepted_id": accepted_id,
        "accepted_value": accepted_value
    })

@app.route("/accept", methods=["POST"])
def accept():
    proposal_id = request.json.get("proposal_id")
    value = request.json.get("value")
    accepted = node.accept(proposal_id, value)
    return jsonify({"accepted": accepted})

@app.route("/learn", methods=["POST"])
def learn():
    value = request.json.get("value")
    node.learn(value)
    return jsonify({"learned": True})

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0", port=5000)
