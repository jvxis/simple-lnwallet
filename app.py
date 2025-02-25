from flask import Flask, render_template, request, redirect, url_for, session
import grpc
import os
import json
import lightning_pb2 as lnrpc
import lightning_pb2_grpc
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecretkey"


# Criar banco de dados e tabela para armazenar conexões
def init_db():
    conn = sqlite3.connect("nodes.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias TEXT,
            address TEXT UNIQUE,
            macaroon_hex TEXT,
            tls_cert_hex TEXT
        )
    """)
    conn.commit()
    conn.close()
# Chamar a função para garantir que o banco está criado
init_db()

# Salvar um novo node no banco
def save_node(alias, address, macaroon_hex, tls_cert_hex):
    conn = sqlite3.connect("nodes.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO nodes (alias, address, macaroon_hex, tls_cert_hex) VALUES (?, ?, ?, ?)", 
                       (alias, address, macaroon_hex, tls_cert_hex))
        conn.commit()
    except sqlite3.IntegrityError:
        print("⚠️ Este node já está salvo!")
    finally:
        conn.close()

# Buscar nodes cadastrados
def get_nodes():
    conn = sqlite3.connect("nodes.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nodes")
    nodes = cursor.fetchall()
    conn.close()
    return nodes

def connect_lnd(node_address, macaroon_hex, tls_cert_hex):
    os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'

    # Converter o TLS de HEX para bytes
    try:
        tls_cert_bytes = bytes.fromhex(tls_cert_hex)
    except ValueError:
        raise ValueError("Formato inválido do TLS HEX. Verifique se copiou corretamente.")

    # Criar credenciais gRPC com root certificates
    cert_creds = grpc.ssl_channel_credentials(root_certificates=tls_cert_bytes)

    # Criar credenciais de autenticação com macaroon
    def metadata_callback(context, callback):
        callback([("macaroon", macaroon_hex)], None)
    auth_creds = grpc.metadata_call_credentials(metadata_callback)

    creds = grpc.composite_channel_credentials(cert_creds, auth_creds)

    # Criar canal gRPC com bypass de hostname
    options = (("grpc.ssl_target_name_override", "localhost"),)
    channel = grpc.secure_channel(node_address, creds, options=options)

    stub = lightning_pb2_grpc.LightningStub(channel)
    return stub

@app.route('/', methods=['GET', 'POST'])
def index():
    nodes = get_nodes()  # Buscar nodes cadastrados no banco
    error_message = None  # Inicializa erro como None

    if request.method == 'POST':
        node_address = request.form['node_address']
        macaroon_hex = request.form['macaroon_hex']
        tls_cert_hex = request.form['tls_cert_hex']
        
        # Tenta conectar para obter alias
        stub = connect_lnd(node_address, macaroon_hex, tls_cert_hex)
        try:
            response = stub.GetInfo(lnrpc.GetInfoRequest())
            alias = response.alias
        except Exception as e:
            error_message = f"⚠️ Erro ao conectar ao node: {e}"
            print(f"Erro de conexão: {e}")  # Loga no terminal
            return render_template('index.html', nodes=nodes, error_message=error_message)
        
        # Salvar node no banco
        save_node(alias, node_address, macaroon_hex, tls_cert_hex)
        
        # Salvar na sessão
        session['node_address'] = node_address
        session['macaroon_hex'] = macaroon_hex
        session['tls_cert_hex'] = tls_cert_hex
        
        return redirect(url_for('dashboard'))

    return render_template('index.html', nodes=nodes, error_message=error_message)

@app.route('/dashboard')
def dashboard():
    if 'node_address' not in session or 'macaroon_hex' not in session or 'tls_cert_hex' not in session:
        return redirect(url_for('index'))
    
    node_address = session['node_address']
    macaroon_hex = session['macaroon_hex']
    tls_cert_hex = session['tls_cert_hex']
    
    stub = connect_lnd(node_address, macaroon_hex, tls_cert_hex)

    try:
        response = stub.GetInfo(lnrpc.GetInfoRequest())
        balance = stub.WalletBalance(lnrpc.WalletBalanceRequest())
        channel_balance = stub.ChannelBalance(lnrpc.ChannelBalanceRequest())

        # Converter os valores booleanos para emojis
        synced_to_chain = "✅" if response.synced_to_chain else "❌"
        synced_to_graph = "✅" if response.synced_to_graph else "❌"

        return render_template('dashboard.html', 
            node_info=response, 
            balance=balance, 
            channel_balance=channel_balance,
            synced_to_chain=synced_to_chain, 
            synced_to_graph=synced_to_graph
        )
    except Exception as e:
        print(f"Erro ao conectar ao LND: {e}")
        return f"Erro ao conectar ao LND: {e}"


@app.route('/invoice', methods=['GET', 'POST'])
def invoice():
    if 'node_address' not in session or 'macaroon_hex' not in session or 'tls_cert_hex' not in session:
        return redirect(url_for('index'))

    node_address = session['node_address']
    macaroon_hex = session['macaroon_hex']
    tls_cert_hex = session['tls_cert_hex']  # Adicionado aqui

    stub = connect_lnd(node_address, macaroon_hex, tls_cert_hex)  # Passando os 3 argumentos corretamente

    if request.method == 'POST':
        amount = int(request.form['amount'])
        memo = request.form['memo']

        try:
            invoice_request = lnrpc.Invoice(value=amount, memo=memo)
            response = stub.AddInvoice(invoice_request)
            return render_template('invoice.html', invoice=response.payment_request)
        except Exception as e:
            return f"Erro ao criar fatura: {e}"

    return render_template('invoice.html')


@app.route('/pay', methods=['GET', 'POST'])
def pay():
    if 'node_address' not in session or 'macaroon_hex' not in session or 'tls_cert_hex' not in session:
        return redirect(url_for('index'))

    node_address = session['node_address']
    macaroon_hex = session['macaroon_hex']
    tls_cert_hex = session['tls_cert_hex']

    stub = connect_lnd(node_address, macaroon_hex, tls_cert_hex)

    if request.method == 'POST':
        payment_request = request.form['payment_request']

        try:
            pay_request = lnrpc.SendRequest(payment_request=payment_request)
            response = stub.SendPaymentSync(pay_request)

            # 🔹 Criar um dicionário formatado com os atributos relevantes
            response_dict = {
                "payment_preimage": response.payment_preimage.hex(),  # Convertendo bytes para HEX
                "payment_hash": response.payment_hash.hex(),
                "payment_route": {
                    "total_time_lock": response.payment_route.total_time_lock,
                    "total_amt": response.payment_route.total_amt,
                    "hops": [
                        {
                            "chan_id": hop.chan_id,
                            "chan_capacity": hop.chan_capacity,
                            "amt_to_forward": hop.amt_to_forward,
                            "expiry": hop.expiry,
                            "amt_to_forward_msat": hop.amt_to_forward_msat,
                            "pub_key": hop.pub_key
                        }
                        for hop in response.payment_route.hops
                    ]
                }
            }

            return render_template('pay.html', result=response_dict)
        except Exception as e:
            return f"Erro ao pagar fatura: {e}"

    return render_template('pay.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=35671, debug=True)

