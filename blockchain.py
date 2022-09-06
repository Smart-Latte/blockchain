"""
なんちゃってブロックチェーンを生成する
Flask, requestsをインストール
HTTPクライアントを用意（Talend Api Testerを予定）
"""

# coding: UTF-8

import hashlib
import json
from time import time
from uuid import uuid4
from urllib.parse import urlparse

from flask import Flask, jsonify, request
import requests

class Blockchain(object):
    """
    ブロックチェーンを納めるための空のリスト
    トランザクションを納めるための空のリスト
    を作る
    """
    def __init__(self):
        """
        chain: ブロックチェーンのリスト
        current_transactions: トランザクションのリスト
        nodes: ノードのリスト
        ジェネシスブロックを作り、プルーフマイニング(PoW)の結果を加える
        """
        self.chain = []
        self.current_transactions = []
        self.nodes = set() # 新しいノードを何回加えても、一回しか保存されない

        # ジェネシスブロック（先祖を持たないブロック）を作る
        self.new_block(previous_hash=1, proof=100)

    def register_node(self, address):
        """
        ノードリストに新しいノードを加える
        :param address: <str> ノードのアドレス 例：'http://192.168.0.5:5000'
        :return: None
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def new_block(self, proof, previous_hash=None):
        """新しいブロックを作り、チェーンに加える
        :param proof: <int> PoWアルゴリズムから得られるプルーフ
        :param previous_hash: (オプション) <str> 前のブロックのハッシュ
        :return: <dict> 新しいブロック
        """
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
        # 現在のトランザクションリストをリセット
        self.current_transactions = []

        self.chain.append(block)
        return block

    def add_transaction(self, sender, recipient, amount):
        """
        次に採掘されるブロックに加える新しいトランザクションを作る
        新しいトランザクションをリストに加えた後、
        そのトランザクションが加えられるブロック（次に採掘されるブロック）のインデックスを返す
        :param sender: <str> 送信者のアドレス
        :param recipient: <str> 受信者のアドレス
        :param amount: <int> 量
        :return: <int> このトランザクションを含むブロックのアドレス
        """

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        """
        ブロックをハッシュ化する(ブロックのSHA-256ハッシュをつくる)
        :param block: <dict> ブロック
        :return: <str>
        """
        # 必ずディクショナリがソートされている必要がある。そうでないと、一貫性のないハッシュとなる
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        """チェーンの最後のブロックを返す"""
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        """
        シンプルなPoWのアルゴリズム
        - hash(pp')の最初の4つが0となるようなp'を探す
        - pは1つ前のブロックのプルーフ、p'は新しいブロックのプルーフ
        :param last_proof: <int>
        :return: <int>
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        プルーフが正しいか確認: hash(last_proof, proof)の最初の4つが0となっているかどうか
        :param last_proof: <int> 前のプルーフ
        :param proof: <int> 現在のプルーフ
        :return: <bool> 正しければtrue, そうでなければfalse
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()

        return guess_hash[:4] == "0000"

    def valid_chain(self, chain):
        """ブロックチェーンが正しいかどうかを確認する
        :param chain: <list> ブロックチェーン
        :return: <bool> Trueであれば正しく、Falseなら誤り
        """
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n----------------\n")

            # ブロックのハッシュが正しいか確認
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Powが正しいか確認
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        コンセンサスアルゴリズム
        ネットワーク上のもっとも長いチェーンで自らのチェーンを置き換える
        :return: <bool> チェーンが置き換えられるとTrue、置き換えられないとFalse
        """
        neighbours = self.nodes
        new_chain = None

        # 長いチェーンを探すため
        max_length = len(self.chain)

        # 他のすべてのノードのチェーンを確認
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # そのチェーンがより長いか、有効か確認
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # もし自らのチェーンより長く、かつ有効なチェーンを見つけた場合、置き換え
        if new_chain:
            self.chain = new_chain
            return True

        return False


# ノードを作る
app = Flask(__name__)

# このノードの、グローバルでユニークなアドレスをつくる
NODE_IDENTIFIER = str(uuid4()).replace('-', '')

# ブロックチェーンクラスをインスタンス化する
blockchain = Blockchain()

@app.route('/nodes/resister', methods=['POST'])
def resister_new_node():
    """
    nodeを追加するためのエンドポイント
    """
    values = request.get_json()

    new_nodes = values.get('nodes')
    if new_nodes is None:
        return "Error: 有効ではないノードのリストです", 400

    for node in new_nodes:
        blockchain.register_node(node)

    response = {
        'message': '新しいノードが追加されました',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    """コンフリクトを解消するため"""
    replaced = blockchain.resolve_conflicts()

    if replaced: # True
        response = {
            'message': 'チェーンが置き換えられました',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'チェーンが確認されました',
            'new_chain': blockchain.chain
        }

    return jsonify(response), 200

# POST
@app.route('/transactions/new', methods=['POST'])
def new_transactions():
    """新しいトランザクションを受け付け"""
    values = request.get_json()

    # POSTされたデータに必要なデータがあるか確認
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # 新しいトランザクションを作る
    index = blockchain.add_transaction(values['sender'], values['recipient'], values['amount'])
    response = {'message': f'トランザクションはブロック{index}に追加されました'}
    return jsonify(response), 201

# GETで/mineエンドポイントをつくる
@app.route('/mine', methods=['GET'])
def mine():
    """次のプルーフを見つけるためにPowアルゴリズムを使用"""
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # プルーフを見つけたことに対する報酬を得る
    # 送信者は、採掘者が新しいコインを採掘したことを表すために"0"とする
    blockchain.add_transaction(
        sender="0",
        recipient=NODE_IDENTIFIER,
        amount=1,
    )

    # チェーンに新しいブロックを加えることで、新しいブロックを採掘する
    block = blockchain.new_block(proof)

    response = {
        'message': '新しいブロックを採掘しました',
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

# GETで、フルのブロックチェーンをリターンする/chainエンドポイントをつくる
@app.route('/chain', methods=['GET'])
def full_chain():
    """ブロックチェーンをリターン"""
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
