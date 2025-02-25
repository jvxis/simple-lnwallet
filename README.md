# ⚡ Lightning Wallet CLI

Este é um **serviço web minimalista de carteira Lightning Network** que se conecta a um node LND via gRPC.  
Ele permite visualizar informações do node, criar faturas e pagar invoices.

🚀 **Tecnologias usadas**:
- Python + Flask
- gRPC (para comunicação com LND)
- SQLite3 (armazenamento de nodes)
- QR Code para pagamento

---

## 📌 **1. Requisitos**
Antes de começar, certifique-se de ter:
- **Python 3.8 ou superior** instalado.
- **Acesso ao seu LND via gRPC** (porta `10009`).
- **Admin Macaroon e TLS Cert em formato HEX**.

Se estiver no **Raspberry Pi 4**, instale `xxd` para extrair os arquivos:
```bash
sudo apt update && sudo apt install xxd -y
```
## **2. Instalando as dependências**
Clone este repositório e instale os pacotes:

```bash
git clone https://github.com/seu-usuario/lightning-wallet.git
cd lightning-wallet
python3 -m venv venv
source venv/bin/activate  # No Windows use: venv\Scripts\activate
pip3 install -r requirements.txt
```
## **3. Extraindo as Credenciais do LND**
Executar no diretório `/home/admin`
```bash
xxd -p ~/.lnd/data/chain/bitcoin/mainnet/admin.macaroon | tr -d '\n' > macaroon.hex
xxd -p ~/.lnd/tls.cert | tr -d '\n' > tls.hex
```
## **4. Executando a Aplicação**
Utilize uma VPN ou Tailscale por questão de segurança
Na máquina host execute:
```bash
python3 app.py
```
**Você acessa a app com http://nome-maquina:35671**
